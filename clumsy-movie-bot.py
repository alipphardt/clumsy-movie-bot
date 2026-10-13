###############################################
#               Dependencies                  #
###############################################

# Standard python libraries
import io
import os
import sys
import random
import pytz
from datetime import datetime, timedelta
# Third party libraries
import discord
from discord.ext import commands
import pandas as pd
import requests
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns

from discord_helpers import chunk_lines
from tmdb import (
    build_auth_headers,
    build_find_by_imdb_id_url,
    build_movie_details_url,
    build_search_movie_url,
    build_tmdb_movie_url,
    extract_first_movie_result_id,
    format_search_results_message,
    is_random_candidate_allowed,
    parse_movie_summary,
    parse_search_results,
)
from voting_logic import (
    build_holdover_titles,
    build_weighted_wheel_titles,
    build_wheel_text_chunks,
    DEFAULT_OLDEST_EXCLUDED_TITLES,
    calculate_vote_totals,
    classify_rollover_and_fallen,
    collect_current_nomination_titles,
    count_movie_nominations,
    count_total_votes,
    find_first_seen_titles,
    format_oldest_title_lines,
    merge_fallen_titles,
    top_oldest_titles,
)
from wheel_of_names import (
    WHEEL_API_V3_URL,
    build_delete_wheel_url,
    build_list_wheels_params,
    build_sanitized_wheel_title_lines,
    build_wheel_entries,
    build_wheel_payload,
    build_wheel_share_url,
    extract_wheel_path,
    extract_wheel_paths,
)


###############################################
#               Initialization                #
###############################################


# Global running list of winning movie titles for the current week
titles = []

# Global list of movies returned from TMDB
movies = []
holdover_df = []
fallen_df = []

def load_dataframes():
    """Load CSV-backed bot dataframes."""
    return {
        'bmovies_df': pd.read_csv('bmovies.csv', dtype = {'ID': str}),
        'winners_df': pd.read_csv('clumsy-movie-winners.csv', dtype = str),
        'holdover_df': pd.read_csv('holdover.csv', dtype = {'Movie': str}),
        'fallen_df': pd.read_csv('fallen.csv', dtype = {'Movie': str}),
    }


# List of past winners, stored in clumsy-movie-winners.csv
_dataframes = load_dataframes()
bmovies_df = _dataframes['bmovies_df']
winners_df = _dataframes['winners_df']
holdover_df = _dataframes['holdover_df']
fallen_df = _dataframes['fallen_df']

def load_config(environ=None):
    """Load bot configuration from environment variables."""
    environ = environ or os.environ
    return {
        'TOKEN': environ['DISCORD_BOT_TOKEN'],
        'CHANNEL_ID': int(environ['DISCORD_MOVIES_CHANNEL']),
        'TERMINAL_ID': int(environ['DISCORD_TERMINAL_CHANNEL']),
        'TEST_ID': int(environ['DISCORD_TEST_CHANNEL']),
        'API_KEY': environ['WHEEL_API_KEY'],
        'TMDB_TOKEN': environ['TMDB_TOKEN'],
    }


# Account/channel specific information stored as environmental variable
config = load_config()
TOKEN = config['TOKEN']
CHANNEL_ID = config['CHANNEL_ID']
TERMINAL_ID = config['TERMINAL_ID']
TEST_ID = config['TEST_ID']
API_KEY = config['API_KEY']
TMDB_TOKEN = config['TMDB_TOKEN']


def lastSaturday():

    rolltime = pd.read_csv('rollover-time.csv', parse_dates=['Time'])
    rolltime['Time'] = rolltime['Time'].dt.tz_localize(None)
    return rolltime['Time'][0]


async def isTerminal(ctx):
    """ Custom check used in all commands to limit bot commands to skynet terminal OR clumsy testing server """

    if(ctx.command.name in ['rollover', 'holdover', 'print_holdover']):
        return True

    if(ctx.command.name == 'samples'):
        return ctx.channel.id == TERMINAL_ID

    return ctx.channel.id == TERMINAL_ID or ctx.channel.id == TEST_ID


def message_to_vote_record(message):
    """Convert a Discord message into the simple shape used by voting logic."""
    return {
        'content': message.content,
        'reaction_counts': [reaction.count for reaction in message.reactions]
    }


def build_tmdb_embed(movie_id, summary):
    """Build a Discord embed for parsed TMDB movie summary data."""
    embed = discord.Embed(title = summary['title'],
                          description = summary['description'],
                         colour = discord.Colour.blue(),
                         url = build_tmdb_movie_url(movie_id))

    embed.add_field(name = 'Release Date', value = summary['release_date'], inline = True)
    embed.add_field(name = 'Runtime (min)', value = summary['runtime'], inline = True)

    if summary['poster_url'] != '':
        try:
            embed.set_image(url=summary['poster_url'])
        except KeyError:
            pass

    return embed


# All commands for bot will be prefixed with a period (e.g. '.help')
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix = '.', intents=intents)
client.add_check(isTerminal)



###############################################
#               WHEEL/VOTING                  #
###############################################


class Voting(commands.Cog, name='1: Voting'):
    """Commands to read and summarize movie nominations and voting"""

    def __init__(self, bot):
        self.bot = bot


    @commands.command(brief='Tally votes', 
                    description='Generates a bar chart of votes for all movies that received at least one reaction since last Saturday at 10:00 (UTC time)')
    async def tally(self, ctx):
        await ctx.send("Tabulating votes...")

        channel = client.get_channel(CHANNEL_ID)

        # Add movies and number of reactions (i.e. votes) and sort in descending order

        nomination_messages = []

        async for message in channel.history(after=lastSaturday()):
            nomination_messages.append(message_to_vote_record(message))

        votes = calculate_vote_totals(nomination_messages, titles)

        if not votes:
            await ctx.send("No votes found since last rollover.")
            return

        votes = pd.DataFrame.from_records(votes, columns = ['Movie', 'Number of Votes'])

        votes["Number of Votes"] = pd.to_numeric(votes["Number of Votes"])
        votes.sort_values(by = "Number of Votes", ascending = False, inplace = True)
        votes['Movie_Trunc'] = votes['Movie'].apply(lambda x: x[:25] + '…' if len(x) > 25 else x)

        sns.set(style="whitegrid")
        figure_height = min(max(3, len(votes) * 0.5), 20)
        fig, ax = plt.subplots(figsize=(10, figure_height))
        sns.barplot(x='Number of Votes', y='Movie_Trunc', data=votes, color='steelblue', ax=ax)

        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        max_votes = votes['Number of Votes'].max()
        ax.set_xlim(0, max_votes * 1.15)
        xlim = ax.get_xlim()
        offset = (xlim[1] - xlim[0]) * 0.01  # 1% of axis width

        for i, value in enumerate(votes['Number of Votes']):
            ax.text(value + offset, i, str(value), va='center')

        ax.set_xlabel('Votes')
        ax.set_ylabel('Movie')
        ax.set_title('Clumsy Movie Ranking (as of ' + datetime.now().strftime("%m/%d/%Y, %H:%M") + ')')
        fig.tight_layout()

        fig.savefig('./discord-images/graph.png', dpi=150, bbox_inches='tight')
        plt.close(fig)

        with open('./discord-images/graph.png', 'rb') as f:
            file = io.BytesIO(f.read())

        image = discord.File(file, filename='graph.png')
        embed = discord.Embed(title = "Votes as of " + datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
        embed.set_image(url='attachment://graph.png')

        await ctx.send(file=image, embed=embed)


    @commands.command(
        brief='Top 10 oldest nominated movies',
        description='Finds the 10 oldest movies (based on first appearance in channel history) among titles nominated since last rollover'
    )
    async def oldest(self, ctx):

        await ctx.send("Scanning message history (this may take a bit)...")

        channel = client.get_channel(CHANNEL_ID)

        # Step 1: Collect titles since last rollover
        recent_messages = []
        excluded_titles = set(titles).union(DEFAULT_OLDEST_EXCLUDED_TITLES)

        async for message in channel.history(after=lastSaturday()):
            recent_messages.append({'content': message.content})

        current_titles = collect_current_nomination_titles(recent_messages, excluded_titles)

        if not current_titles:
            await ctx.send("No titles found since last rollover.")
            return

        # Step 2: Scan full history once to find earliest occurrence of each title
        first_seen = {}

        async for message in channel.history(limit=None, oldest_first=True):
            first_seen.update(find_first_seen_titles([{
                'content': message.content,
                'created_at': message.created_at
            }], current_titles - set(first_seen)))

            # Optimization: stop early if we've found all titles
            if len(first_seen) == len(current_titles):
                break

        if not first_seen:
            await ctx.send("No matching historical messages found.")
            return

        # Step 3: Sort by oldest timestamp and format output
        top_10 = top_oldest_titles(first_seen)
        lines = format_oldest_title_lines(top_10)

        for chunk in chunk_lines("Top 10 Oldest Movies (by first appearance):\n", lines):
            await ctx.send(chunk)


    @commands.command(brief='Count votes',
                    description='Calculate the total number of all votes since the last rollover')
    async def votecount(self, ctx):

        channel = client.get_channel(CHANNEL_ID)

        # Add movies and number of reactions (i.e. votes) and sort in descending order

        nomination_messages = []

        async for message in channel.history(after=lastSaturday()):
            nomination_messages.append(message_to_vote_record(message))

        number_of_votes = count_total_votes(nomination_messages, titles)

        await ctx.send(f'Number of votes: {number_of_votes}')


    @commands.command(brief='Count movies nominated', description='Counts all movie nominations since the last rollover, excluding rollover header messages')
    async def moviecount(self, ctx):

        channel = client.get_channel(CHANNEL_ID)
        nomination_messages = []

        async for message in channel.history(after=lastSaturday()):
            nomination_messages.append({'content': message.content})

        number_of_movies = count_movie_nominations(nomination_messages)

        await ctx.send("Number of movies: " + str(number_of_movies) + "\n")


    @commands.command(brief='Send list to wheel of names', description='Generates a list for all movies that received at least one reaction since last rollover. Movie titles are duplicated according to number of votes. List is compiled into JSON and submitted to wheel of names application.')
    async def wheel(self, ctx):

        channel = client.get_channel(CHANNEL_ID)

        # Create a text list of all movie titles, copied according to number of votes

        nomination_messages = []

        await ctx.send("Preparing list for wheel of names...")

        async for message in channel.history(after=lastSaturday()):
            nomination_messages.append(message_to_vote_record(message))

        vote_totals = calculate_vote_totals(nomination_messages, titles)
        wheel_list = build_weighted_wheel_titles(vote_totals)
        sanitized_lines = build_sanitized_wheel_title_lines(list(dict.fromkeys(wheel_list)))

        if sanitized_lines:
            for chunk in chunk_lines("Sanitizing titles for Wheel of Names:\n", sanitized_lines):
                await ctx.send(chunk)

        entries = build_wheel_entries(wheel_list)
        wheel = build_wheel_payload(entries)

        headers = {
            'x-api-key': API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(WHEEL_API_V3_URL, headers=headers, json=wheel)

        if(not response.ok):
            await ctx.send(response.status_code)
            await ctx.send(response.text)
            await ctx.send("Wheel List:\n")

            for chunk in build_wheel_text_chunks(vote_totals):
                await ctx.send(chunk)
        else:
            await ctx.send("Submitted. Go to " + build_wheel_share_url(extract_wheel_path(response.json())))



    @commands.command(brief='Send fallen list to wheel of names', description='Generates a list of movies from the fallen list. List is compiled into JSON and submitted to wheel of names application.')
    async def wheel_fallen(self, ctx):

        channel = client.get_channel(CHANNEL_ID)

        # Create a text list of all movie titles, copied according to number of votes
        global fallen_df
        wheel_list = fallen_df['Movie'].tolist()

        await ctx.send("Preparing list for wheel of names...")

        sanitized_lines = build_sanitized_wheel_title_lines(wheel_list)

        if sanitized_lines:
            for chunk in chunk_lines("Sanitizing titles for Wheel of Names:\n", sanitized_lines):
                await ctx.send(chunk)

        entries = build_wheel_entries(wheel_list)
        wheel = build_wheel_payload(entries)

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': API_KEY
        }

        response = requests.post(WHEEL_API_V3_URL, headers=headers, json=wheel)

        if(not response.ok):
            await ctx.send(f"Something went wrong (Status: {response.status_code})")
            await ctx.send(response.text)
        else:
            await ctx.send("Submitted. Go to " + build_wheel_share_url(extract_wheel_path(response.json())))


    @commands.command(brief='Purge shared wheels', description='Deletes all shared wheels associated with API key')
    async def wheel_purge(self, ctx):

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': API_KEY
        }

        response = requests.get(WHEEL_API_V3_URL, headers=headers, params=build_list_wheels_params())

        if(not response.ok):
            await ctx.send(f"Wheel list failed (Status: {response.status_code})")
            await ctx.send(response.text)
            return

        for path in extract_wheel_paths(response.json()):
            response = requests.delete(build_delete_wheel_url(path), headers=headers)

            if(not response.ok):
                await ctx.send(path + ' purge failed')
            else:
                await ctx.send(path + ' purge complete')


    @commands.command(brief='Excludes winning movie from the rollover', description='Add winning movie for the current week to a temporary list of winners that should be excluded from rollover. Run prior to rollover function.')
    async def exclude(self, ctx, *, title: str):

        global titles
        titles.append(title)

        await ctx.send("Excluded from rollover: " + title)


    @commands.command(brief='Added winning movie to permanent winning list', description='Add winning movie for the current week to a permanent list of winners. Use index from most recent TMDB search to store title and TMDB ID.')
    async def winner(self, ctx, index: int):

        global movies
        global winners_df
        index = int(index) - 1
        imdb_id = ''

        try:
            movieID = movies[index]['id']

            url = build_movie_details_url(movieID)
            headers = build_auth_headers(TMDB_TOKEN)
            resp = requests.get(url=url, headers=headers)
            data = resp.json()
            imdb_id = data.get('imdb_id','')

        except IndexError:
            await ctx.send("Please run .tmdb command first to store list of movies")
            return

        await ctx.send("Added to Permanent Movie List: " + movies[index]['title'])

        new_row = pd.DataFrame([{'title': movies[index]['title'], 'imdb_id': imdb_id, 'tmdb_id': movieID}])
        winners_df = pd.concat([winners_df, new_row], ignore_index=True)
        winners_df.to_csv('clumsy-movie-winners.csv', index = False)


    @commands.command(brief='List winners', description='Print the list of winners to be excluded from .rollover command')
    async def exclude_list(self, ctx):

        global titles
        await ctx.send(titles)


    @commands.command(brief='Clear winners', description='Clear the winners list used in the .rollover command')
    async def winner_clear(self, ctx):

        global titles
        titles = []


    @commands.command(brief='Display past winners', description='Display a list of past winners')
    async def winners(self, ctx):

        global winners_df

        lines = []

        for i in range(len(winners_df)):
            lines.append("[" + str(i+1) + "] " + winners_df.iloc[i]['title'] + "\n")

        for chunk in chunk_lines("Clumsy Movie Past Showings:\n", lines):
            await ctx.send(chunk)


#     @commands.command(brief='Create a rollover list', description='Create a rollover list for the next week, with movies that have at least 1 vote. NOTE: Add winners to winner list first with winner command')
#     async def rollover(self, ctx):
#
#         # Grab rollover time just before writing rollover list
#         rollover_time = datetime.utcnow().replace(tzinfo = pytz.utc)
#
#         await ctx.send("Next Week on the Wheel:")
#
#         channel = client.get_channel(CHANNEL_ID)
#
#         rollover_list = []
#
#         async for message in channel.history(after=lastSaturday()):
#             if len(message.reactions) > 0 and message.content not in titles:
#                 rollover_list.append(message.content)
#
#         for movie in sorted(rollover_list):
#             await ctx.send(movie)
#
#         # Write rollover time to an external file
#         time_pd = pd.DataFrame(data = {'Time': [rollover_time]})
#         time_pd.to_csv('rollover-time.csv', index = False)


    @commands.command(brief='Create a rollover list', description='Create a rollover list for the next week, with movies that have at least 2 unique voters. NOTE: Add winners to winner list first with winner command')
    async def rollover(self, ctx):

        # Grab rollover time just before writing rollover list
        rollover_time = datetime.utcnow().replace(tzinfo = pytz.utc)

        global fallen_df

        await ctx.send("Next Week on the Wheel:")
        channel = client.get_channel(CHANNEL_ID)

        nomination_messages = []

        async for message in channel.history(after=lastSaturday()):
            #await test_channel.send("Checking: " + message.content)
            unique_users = set()
            for reaction in message.reactions:
                users = [user async for user in reaction.users()]
                unique_users.update(users)
                if(len(unique_users) > 1):
                    break

            nomination_messages.append({
                'content': message.content,
                'unique_voter_count': len(unique_users)
            })

        rollover_list, fallen_list = classify_rollover_and_fallen(nomination_messages, titles)

        # To the rollover
        for movie in sorted(rollover_list):
            #await test_channel.send(movie)
            await ctx.send(movie)

        # To the fallen

        movies = merge_fallen_titles(fallen_df['Movie'], fallen_list)

        fallen_df = pd.DataFrame(movies, columns = ['Movie'])
        fallen_df.to_csv('fallen.csv', index=False)

        # Write rollover time to an external file
        time_pd = pd.DataFrame(data = {'Time': [rollover_time]})
        time_pd.to_csv('rollover-time.csv', index = False)


    @commands.command(brief='Print the fallen list', description='Print a list of previously nominated movies that held votes from 0 or 1 voters at the time they were removed.')
    async def fallen(self, ctx):

        global fallen_df

        movies = list(fallen_df['Movie'])

        lines = []

        for i in range(len(movies)):
            lines.append("[" + str(i+1) + "] " + movies[i] + "\n")

        for chunk in chunk_lines("The Fallen:\n", lines):
            await ctx.send(chunk)

        with open('./discord-images/fallen.jpg', 'rb') as f:
            file = io.BytesIO(f.read())

        image = discord.File(file, filename='fallen.jpg')
        embed = discord.Embed(title = "We salute the fallen")
        embed.set_image(url=f'attachment://fallen.jpg')

        await ctx.send(file=image, embed=embed)


    @commands.command(brief='Random movie from The Fallen', description='Shuffle The Fallen list and randomly select a movie')
    async def random_fallen(self, ctx):

        global fallen_df

        movies = list(fallen_df['Movie'])
        movie_index = random.randint(0, len(movies)-1)

        await ctx.send(f"[{movie_index+1}] {movies[movie_index]}")


    @commands.command(brief = 'Remove a specified move from The Fallen', description = 'After running .fallen or .random_fallen command, use the .remove_fallen <index> command to remove the specified movie from The Fallen list.')
    async def remove_fallen(self, ctx, index):

        try:
            global fallen_df
            index = int(index) - 1

            movies = list(fallen_df['Movie'])
            movie = movies.pop(index)

            # Sort remaining movies and write back to The Fallen
            fallen_df = pd.DataFrame(movies, columns = ['Movie'])
            fallen_df.to_csv('fallen.csv',index=False)

            await ctx.send(f"Removed from The Fallen: {movie}")

        except IndexError:
            await ctx.send("Please run .fallen or .random_fallen command to see list of movies on The Fallen")
            return


    @commands.command(brief='Create a holdover list', description='Create a holdover list for the next week, with movies that have at least 1 vote. NOTE: Add winners to winner list first with winner command')
    async def holdover(self, ctx):

        # Grab rollover time just before writing rollover list
        rollover_time = datetime.utcnow().replace(tzinfo = pytz.utc)

        global holdover_df

        channel = client.get_channel(CHANNEL_ID)

        nomination_messages = []

        async for message in channel.history(after=lastSaturday()):
            nomination_messages.append(message_to_vote_record(message))

        holdover_list = build_holdover_titles(nomination_messages, titles)
        holdover_df = pd.DataFrame(holdover_list, columns = ['Movie'])
        holdover_df.to_csv('holdover.csv', index=False)

        # Write rollover time to an external file
        time_pd = pd.DataFrame(data = {'Time': [rollover_time]})
        time_pd.to_csv('rollover-time.csv', index = False)

        await ctx.send("Holdover list created successfully")
        await ctx.send("Next Week on the Wheel:")


    @commands.command(brief='Print a holdover list', description='Print a list of movies held over from prior weeks. Used when a list of movies is held over for a later date in lieu of special event spins (e.g. Halloween)')
    async def print_holdover(self, ctx):

        global holdover_df

        # Grab rollover time just before writing rollover list
        rollover_time = datetime.utcnow().replace(tzinfo = pytz.utc)

        # Write rollover time to an external file
        time_pd = pd.DataFrame(data = {'Time': [rollover_time]})
        time_pd.to_csv('rollover-time.csv', index = False)

        await ctx.send("Next Week on the Wheel:")

        for movie in list(holdover_df['Movie']):
            await ctx.send(movie)


    @commands.command(brief='Generate custom BINGO card', description='Generate an image of a custom 5x5 BINGO card for movie night')
    async def bingo(self, ctx):

        items = [
            "cringey romantic\nrelationships",
            "a debate or discussion\nabout the rules of movie\nnight",
            "someone groans or\ncomplains about\nthe movie more\nthan 3 times",
            "“who voted for this?!”",
            "the wheel punishes us for\nour sins or hubris",
            "a random bot or fallen\nmovie wins",
            "really awful soundtrack",
            "really great soundtrack",
            "someone recognizes an\nactor from a different\nmovie/show",
            "someone finds the\nconnection between\nthe two wheel movies",
            "a movie with fewer\nthan 4 votes wins",
            "bodily fluids\non screen",
            "titular line",
            "reference to a\nprevious wheel movie",
            "someone threatens to\nadd a movie to the wheel\n(must be framed\nas a threat)",
            "someone talks about\ntheir kids or pets",
            "gross food scene",
            "unintentionally funny\nsex scene",
            "someone expresses\nconfusion about something\nrecently explained\nor is currently being\nexplained in the movie",
            "lobbying for votes",
            "literal LOLs",
            "anachronisms in\nthe movie",
            "stream needs to be\nrestarted for\naudio issues",
            "delicious looking\nfood on screen",
            "the movie with the\nmost votes wins",
            "wheel is\nvery decisive",
            "disturbing\nsex scene",
            "unintentionally funny\nspecial effects\nor makeup",
            "product placement\nin the movie",
            "monologue lasts\nmore than a minute",
            "more than five\nminutes go by\nwithout dialogue",
            "way too long\ndriving scene",
            "movie generates\nethical, political, or\nphilosophical debate",
            "scene in movie\ndid NOT age well",
            "Boomer joke",
            "someone in the\nmovie sings",
            "DENNIS system",
            "“Yabbos!“",
            "male nudity",
            "“whaddup it’s ya boi“",
            "Star Trek reference",
            "musical instruments\n(in movie or conversation)",
            "someone references BINGO",
            "hot mic\n(eating food,\nbackground talk)",
            "found movie\non YouTube",
            "bad dubbing\n(foreign language, ADR,\nvoiceover)",
            "someone falls asleep\nstill on stream\nnext day",
            "Nic Cage",
            "Willem DaFoe",
            "Patrick Swayze",
            "“Fart movie“ reference",
            "horrendous CGI",
            "obvious stock footage",
            "overuse of\nDutch angles",
            "continuity error",
            "talking animals",
            "movie fails the Bechdel test",
            "movie directly references\na much better movie"

        ]

        # Shuffle items in list
        random.shuffle(items)

        # Take the first 25 items from the shuffled list
        bingo_card = items[:25]

        # Reshape list into a 5x5 grid
        bingo_card = [bingo_card[i:i+5] for i in range(0, len(bingo_card), 5)]
        bingo_card[2][2] = "FREE"

        username = ctx.author.name

        # Create the plot and set the axis labels
        fig, ax = plt.subplots(nrows=5, ncols=5, figsize=(18,12))
        fig.subplots_adjust(hspace=0.3)
        fig.suptitle(f'\nBINGO Scorecard for {username}', fontsize=24)

        # Add labels to each cell
        for i in range(5):
            for j in range(5):
                ax[i,j].axis('on')
                ax[i,j].xaxis.set_tick_params(labelbottom=False, colors="white")
                ax[i,j].yaxis.set_tick_params(labelleft=False, colors="white")
                ax[i,j].text(0.5,0.5, bingo_card[i][j], ha="center", va="center", fontsize=12, wrap=True)

        fig.savefig("./discord-images/scorecard.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

        with open('./discord-images/scorecard.png', 'rb') as f:
            file = io.BytesIO(f.read())

        image = discord.File(file, filename='scorecard.png')
        embed = discord.Embed(title = f'Scorecard for {username}')
        embed.set_image(url=f'attachment://scorecard.png')

        await ctx.send(file=image, embed=embed)


###############################################
#               TMDB COMMANDS                 #
###############################################


class TMDB_Queries(commands.Cog, name='2: TMDB Queries'):
    """Query the TMDB movie database"""


    def __init__(self, bot):
        self.bot = bot


    @commands.command(brief = 'Run TMDB search for specified title', description = 'Returns the top 10 results from TMDB for using the specified title as the search query')
    async def tmdb(self, ctx, *, title: str):

        global movies
        movies = []

        await ctx.send("One moment please...")

        url = build_search_movie_url(title)
        headers = build_auth_headers(TMDB_TOKEN)
        resp = requests.get(url=url, headers=headers)

        try:
            data = resp.json()
            movies = parse_search_results(data)
            results = format_search_results_message(movies)
        except Exception as e:
            results = f"Error (Status Code: {resp.status_code}): {e}"

        await ctx.send(results)


    @commands.command(brief = 'Show TMDB summary for selected movie', description = 'After running .tmdb command, use the .tmdb_summary <index> command to display the TMDB summary for a selected movie. If the .tmdb command has not been run previously, an error message will be produced.')
    async def tmdb_summary(self, ctx, index):

        global movies

        try:
            index = int(index) - 1
            movieID = movies[index]['id']

            url = build_movie_details_url(movieID)
            headers = build_auth_headers(TMDB_TOKEN)
            resp = requests.get(url=url, headers=headers)
            movie = resp.json()

        except IndexError:
            await ctx.send("Please run .tmdb command first to store list of movies")
            return
        except Exception as e:
            await ctx.send(f"Error (Status Code: {resp.status_code}): {e}")
            return

        summary = parse_movie_summary(movie)
        embed = build_tmdb_embed(movieID, summary)

        await ctx.send(embed=embed)


    @commands.command(brief = 'Select random B-movie from TMDB Top 1000', description = '')
    async def random(self, ctx):
        global bmovies_df
        bmovie_ids = bmovies_df['ID'].values

        while True:
            index = random.randint(0,len(bmovie_ids)-1)
            movieID = f'tt{bmovie_ids[index]}'

            try:

                url = build_find_by_imdb_id_url(movieID)
                headers = build_auth_headers(TMDB_TOKEN)
                params = {
                    "external_source": "imdb_id",
                    "language": "en-US"
                }
                resp = requests.get(url=url, headers=headers, params=params)
                movie = resp.json()

                movieID = extract_first_movie_result_id(movie)
                url = build_movie_details_url(movieID)
                resp = requests.get(url=url, headers=headers)
                movie = resp.json()

            except IndexError:
                continue
            except Exception as e:
                await ctx.send(f"Error (Status Code: {resp.status_code}): {e}")
                return

            if is_random_candidate_allowed(movie):
                break

        summary = parse_movie_summary(movie)
        embed = build_tmdb_embed(movieID, summary)

        await ctx.send(embed=embed)


###############################################
#               UTILITY COMMANDS              #
###############################################


class Utility(commands.Cog, name='3: Utility'):
    """Helper commands to facilitate testing or manage bot"""

    def __init__(self, bot):
        self.bot = bot


    @commands.command(brief='Force logout for bot', description='Forces the bot to logoff Discord. Convenience function to interrupt process from jupyter notebook')
    async def kill(self, ctx):
        await ctx.send("Thank you for using Clumsy Movie Bot. Goodbye.")
        await self.bot.close()
        sys.exit(0)


    @commands.command(brief='Print 5 sample movies', description='Prints 5 seperate messages with a movie name. Reactions should be added to movie title to register vote.')
    async def samples(self, ctx):

        # Create sample movie nominations with emoji reactions to simulate votes

        channel = client.get_channel(CHANNEL_ID)

        m1 = await channel.send("Lair of the White Worm")
        m2 = await channel.send("Hausu")
        m3 = await channel.send("Hackers")
        m4 = await channel.send("Earth Girls are Easy")
        m5 = await channel.send("50 Shades Darker")

        await m1.add_reaction('\U0001f44d')
        await m2.add_reaction('\U0001f44d')
        await m3.add_reaction('\U0001f44d')
        await m4.add_reaction('\U0001f44d')
        await m5.add_reaction('\U0001f44d')

        await m4.add_reaction('\U0001f600')
        await m5.add_reaction('\U0001f600')

        await m4.add_reaction('\U0001f603')


async def setup_cogs():
    await client.remove_cog('1: Voting')
    await client.add_cog(Voting(client))
    await client.remove_cog('2: TMDB Queries')
    await client.add_cog(TMDB_Queries(client))
    await client.remove_cog('3: Utility')
    await client.add_cog(Utility(client))


# Message bot will print to console when it is connected and ready to receive commands

@client.event
async def on_ready():
    channel = client.get_channel(TEST_ID)

    await setup_cogs()

    ready_msg = f"Ready to comply...\n\nLast Rollover: {lastSaturday()}"
    await channel.send(ready_msg)


def main():
    client.run(TOKEN)


if __name__ == "__main__":
    main()


