###############################################
#               Dependencies                  #
###############################################

# Standard python libraries
import io
import os
import math
import random
import pytz
from datetime import datetime, timedelta
from copy import deepcopy
import requests
import json
import time

# Third party libraries
import discord
from discord.ext import commands, tasks
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams
from imdb import Cinemagoer


###############################################
#               Initialization                #
###############################################

# Global running list of winning movie titles for the current week
titles = []

# Global list of movies returned from IMDB
movies = []
holdover = []
fallen = []

# List of past winners, stored in clumsy-movie-winners.csv
winners = pd.read_csv('/home/pi/clumsy-movie-bot/clumsy-movie-winners.csv', dtype = {'Title':  str, 'ID': str})
holdover = pd.read_csv('/home/pi/clumsy-movie-bot/holdover.csv', dtype = {'Movie': str})
fallen = pd.read_csv('/home/pi/clumsy-movie-bot/fallen.csv', dtype = {'Movie': str})

# Account/channel specific information stored as environmental variable
TOKEN = os.environ['DISCORD_BOT_TOKEN']
CHANNEL_ID = os.environ['DISCORD_MOVIES_CHANNEL']
TERMINAL_ID = os.environ['DISCORD_TERMINAL_CHANNEL']
TEST_ID = os.environ['DISCORD_TEST_CHANNEL']
API_KEY = os.environ['WHEEL_API_KEY']


# Top 1000 B-movies on IMDB by popularity
bmovies = []
for i in range(1,21):
    bmovies.extend(Cinemagoer().get_keyword(keyword='b-movie',page=i))


def lastSaturday():

    rolltime = pd.read_csv('/home/pi/clumsy-movie-bot/rollover-time.csv', parse_dates=['Time'])
    rolltime['Time'] = rolltime['Time'].dt.tz_localize(None)
    return rolltime['Time'][0]


async def isTerminal(ctx):
    
    """ Custom check used in all commands to limit bot commands to skynet terminal OR clumsy testing server """
        
    if(ctx.command.name in ['rollover', 'rollover2', 'holdover', 'print_holdover']):
        return True
    
    global TERMINAL_ID
    return ctx.channel.id == TERMINAL_ID or ctx.channel.id == TEST_ID


# All commands for bot will be prefixed with a period (e.g. '.help')
client = commands.Bot(command_prefix = '.')
client.add_check(isTerminal)



###############################################
#               WHEEL/VOTING                  #
###############################################

client.remove_cog('1: Voting')

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

        votes = []
        number_of_votes = 0

        async for message in channel.history(after=lastSaturday()):
            if len(message.reactions) > 0 and message.content not in titles:
                
                number_of_votes = 0
                
                for reaction in message.reactions:
                    number_of_votes += reaction.count
                
                votes.append((message.content, number_of_votes))

        
        votes = pd.DataFrame.from_records(votes, columns = ['Movie', 'Number of Votes'])
        
        
        votes["Number of Votes"] = pd.to_numeric(votes["Number of Votes"])
        votes.sort_values(by = "Number of Votes", ascending = False, inplace = True)

        # Create horizontal bar chart of movie rankings

        movies = votes["Movie"]
        movies_range = np.arange(len(movies))
        ranking = votes["Number of Votes"]

        rcParams.update({'figure.autolayout': True})
        
        if(len(movies) < 20):
            rcParams.update({'figure.figsize': [16,9]})
        else:
            rcParams.update({'figure.figsize': [18,32]})

        fig, ax = plt.subplots()

        ax.barh(movies_range, ranking, align='center')
        ax.set_yticks(movies_range)
        ax.set_yticklabels(movies)
        ax.invert_yaxis()  # labels read top-to-bottom
        ax.set_xlabel('Number of Votes')
        ax.set_title('Clumsy Movie Ranking ' + "(as of " + datetime.now().strftime("%m/%d/%Y, %H:%M:%S") + ")")

        # Save figure locally and then embed into message 

        fig.savefig('/home/pi/clumsy-movie-bot/discord-images/graph.png')

        with open('/home/pi/clumsy-movie-bot/discord-images/graph.png', 'rb') as f:
            file = io.BytesIO(f.read())    

        image = discord.File(file, filename='graph.png')
        embed = discord.Embed(title = "Votes as of " + datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
        embed.set_image(url=f'attachment://graph.png')

        await ctx.send(file=image, embed=embed)

        
    @commands.command(brief='Count votes', 
                    description='Calculate the total number of all votes since the last rollover')
    async def votecount(self, ctx):

        channel = client.get_channel(CHANNEL_ID)

        # Add movies and number of reactions (i.e. votes) and sort in descending order

        number_of_votes = 0

        async for message in channel.history(after=lastSaturday()):
            if len(message.reactions) > 0 and message.content not in titles:
                
                for reaction in message.reactions:
                    number_of_votes += reaction.count
                
        await ctx.send(f'Number of votes: {number_of_votes}')    


    @commands.command(brief='Count movies nominated', description='Counts all movies currently nominated since the last rollover')
    async def moviecount(self, ctx):

        channel = client.get_channel(CHANNEL_ID)
        number_of_votes = 0

        async for message in channel.history(after=lastSaturday()):                
            number_of_votes += 1

        await ctx.send("Number of movies: " + str(number_of_votes) + "\n") 


    @commands.command(brief='Send list to wheel of names', description='Generates a list for all movies that received at least one reaction since last rollover. Movie titles are duplicated according to number of votes. List is compiled into JSON and submitted to wheel of names application.')
    async def wheel(self, ctx):

        channel = client.get_channel(CHANNEL_ID)
        
        # Create a text list of all movie titles, copied according to number of votes

        wheel_list = []
        number_of_votes = 0

        await ctx.send("Preparing list for wheel of names...")        
        
        async for message in channel.history(after=lastSaturday()):
            if len(message.reactions) > 0 and message.content not in titles:
                
                number_of_votes = 0
                
                for reaction in message.reactions:
                    number_of_votes += reaction.count
                    for i in range(reaction.count):
                        wheel_list.append(message.content)   
                
        entries = []
        for title in wheel_list:
            entries.append({'text': title})

        url = "https://wheelofnames.com/api/v1/wheels/shared"
        
        wheel = {
            "wheelConfig": {
                    "displayWinnerDialog": True,
                    "description": "First movie to 3 spins wins. Click 'Copy this Wheel' to customize.",
                    "title": "Clumsy Movie Night",
                    "allowDuplicates": True,
                    "maxNames": 50,
                    "entries": entries
                },
            "shareMode": "copyable"
            
            }
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': API_KEY
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(wheel))

        if(response.status_code != 200):
            wheel_list = ""
            number_of_votes = 0

            await ctx.send("Wheel List:\n")        
            
            async for message in channel.history(after=lastSaturday()):
                if len(message.reactions) > 0 and message.content not in titles:
                    
                    number_of_votes = 0
                    
                    for reaction in message.reactions:
                        number_of_votes += reaction.count                
                    
                    if(len(wheel_list + (message.content + "\n") * number_of_votes) >= 2000):
                        await ctx.send(wheel_list)
                        wheel_list = ""
                    
                    wheel_list = wheel_list + (message.content + "\n") * number_of_votes    
                    

            await ctx.send(wheel_list) 
        else:   
            await ctx.send("Submitted. Go to https://wheelofnames.com/" + response.json()['data']['path'])        



    @commands.command(brief='Send fallen list to wheel of names', description='Generates a list of movies from the fallen list. List is compiled into JSON and submitted to wheel of names application.')
    async def wheel_fallen(self, ctx):

        channel = client.get_channel(CHANNEL_ID)
        
        # Create a text list of all movie titles, copied according to number of votes
        global fallen
        wheel_list = fallen['Movie'].tolist()

        await ctx.send("Preparing list for wheel of names...")        
                
        entries = []
        for title in wheel_list:
            entries.append({'text': title})

        url = "https://wheelofnames.com/api/v1/wheels/shared"
        
        wheel = {
            "wheelConfig": {
                    "displayWinnerDialog": True,
                    "description": "First movie to 3 spins wins. Click 'Copy this Wheel' to customize.",
                    "title": "Clumsy Movie Night",
                    "allowDuplicates": True,
                    "maxNames": 50,
                    "entries": entries
                },
            "shareMode": "copyable"
            
            }
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': API_KEY
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(wheel))

        if(response.status_code != 200):
            await ctx.send(f"Something went wrong (Status: {response.status_code})")
        else:   
            await ctx.send("Submitted. Go to https://wheelofnames.com/" + response.json()['data']['path'])
            
            
    @commands.command(brief='Purge shared wheels', description='Deletes all shared wheels associated with API key')
    async def wheel_purge(self, ctx):

        channel = client.get_channel(CHANNEL_ID)

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': API_KEY
        }
        
        response = requests.get('https://wheelofnames.com/api/v1/wheels/shared', headers=headers)
        
        for element in response.json()['data']['wheels']:
            path = element['path']
            response = requests.delete(f'https://wheelofnames.com/api/v1/wheels/{path}', headers=headers)
            
            if(response.status_code != 200):
                await ctx.send(path + ' purge failed')
            else:
                await ctx.send(path + ' purge complete')
            


    @commands.command(brief='Added winning movie to temporary winner list', description='Add winning movie for the current week to a temporary list of winners. Run prior to rollover function.')
    async def winner(self, ctx, *, title: str):
        
        global titles
        titles.append(title)
        
        await ctx.send("Added winner: " + title)

        
    @commands.command(brief='Added winning movie to permanent winning list', description='Add winning movie for the current week to a permanent list of winners. Use index from most recent IMDB search to store title and IMDB ID.')
    async def winner2(self, ctx, index: int):

        try:
            global movies
            global winners
            index = int(index) - 1    
            movieID = movies[index].movieID
            movie = Cinemagoer().get_movie(movieID)
        except IndexError:
            await ctx.send("Please run .imdb command first to store list of movies")
            return   

        
        await ctx.send("Added to Permanent Movie List: " + movie['title'])
        
        winners = winners.append({'Title': movie['title'], 'ID': movieID}, ignore_index=True)
        winners.to_csv('/home/pi/clumsy-movie-bot/clumsy-movie-winners.csv', index = False)
            
            
    @commands.command(brief='List winners', description='Print the list of winners to be excluded from .rollover command')
    async def winner_list(self, ctx):
        
        global titles
        await ctx.send(titles)
        
        
    @commands.command(brief='Clear winners', description='Clear the winners list used in the .rollover command')
    async def winner_clear(self, ctx):
        
        global titles
        titles = []
        
        
    @commands.command(brief='Display past winners', description='Display a list of past winners')
    async def winners(self, ctx):
        
        global winners
        
        results = "Clumsy Movie Past Showings:\n"
        
        for i in range(len(winners)):
            
            next_movie = "[" + str(i+1) + "] " + winners.iloc[i]['Title'] + "\n"
            
            if( len(results + next_movie) > 2000 ):
                await ctx.send(results)
                results = ""
            
            results += next_movie
            
        
        await ctx.send(results)          
        
        
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
#         time_pd.to_csv('/home/pi/clumsy-movie-bot/rollover-time.csv', index = False)

    @commands.command(brief='Create a rollover list', description='Create a rollover list for the next week, with movies that have at least 2 unique voters. NOTE: Add winners to winner list first with winner command')
    async def rollover(self, ctx):

        # Grab rollover time just before writing rollover list
        rollover_time = datetime.utcnow().replace(tzinfo = pytz.utc)

        global fallen

        await ctx.send("Next Week on the Wheel:")

        channel = client.get_channel(CHANNEL_ID) 
        
        rollover_list = []
        fallen_list = []

        async for message in channel.history(after=lastSaturday()):
            
            unique_users = set()
            for reaction in message.reactions:
                users = await reaction.users().flatten()
                unique_users.update(users)
                if(len(unique_users) > 1):
                    break
            
            if len(unique_users) > 1 and message.content not in titles:
                rollover_list.append(message.content)
            elif len(message.reactions) >= 0 and message.content not in titles:
                if( (message.content != "Next Week on the Wheel:") and (message.content != ".rollover") ):
                    fallen_list.append(message.content)
        
        # To the rollover
        for movie in sorted(rollover_list):
            await ctx.send(movie)
        
        # To the fallen
        
        movies = fallen['Movie']
        movies = set(movies)
        
        for movie in sorted(fallen_list):
            movies.add(movie)
                
        fallen = pd.DataFrame(sorted(movies), columns = ['Movie'])
        fallen.to_csv('/home/pi/clumsy-movie-bot/fallen.csv',index=False)

        # Write rollover time to an external file
        time_pd = pd.DataFrame(data = {'Time': [rollover_time]})
        time_pd.to_csv('/home/pi/clumsy-movie-bot/rollover-time.csv', index = False)


    @commands.command(brief='Print the fallen list', description='Print a list of previously nominated movies that held votes from 0 or 1 voters at the time they were removed.')
    async def fallen(self, ctx):

        global fallen    

        movies = list(fallen['Movie'])

        results = "The Fallen:\n"
        
        for i in range(len(movies)):
            
            next_movie = "[" + str(i+1) + "] " + movies[i] + "\n"
            
            if( len(results + next_movie) > 2000 ):
                await ctx.send(results)
                results = ""
            
            results += next_movie
            
        await ctx.send(results)
            
        with open('/home/pi/clumsy-movie-bot/discord-images/fallen.jpg', 'rb') as f:
            file = io.BytesIO(f.read())    

        image = discord.File(file, filename='fallen.jpg')
        embed = discord.Embed(title = "We salute the fallen")
        embed.set_image(url=f'attachment://fallen.jpg')

        await ctx.send(file=image, embed=embed)            


    @commands.command(brief='Random movie from The Fallen', description='Shuffle The Fallen list and randomly select a movie')
    async def random_fallen(self, ctx):

        global fallen
        
        movies = list(fallen['Movie'])
        movie_index = random.randint(0, len(movies)-1)
        
        await ctx.send(f"[{movie_index+1}] {movies[movie_index]}")
              

    @commands.command(brief = 'Remove a specified move from The Fallen', description = 'After running .fallen or .random_fallen command, use the .remove_fallen <index> command to remove the specified movie from The Fallen list.')
    async def remove_fallen(self, ctx, index):

        try:
            global fallen
            index = int(index) - 1
            
            movies = list(fallen['Movie'])
            movie = movies.pop(index)
            
            fallen = movies
        
            # Sort remaining movies and write back to The Fallen
            fallen = pd.DataFrame(fallen, columns = ['Movie'])
            fallen.to_csv('/home/pi/clumsy-movie-bot/fallen.csv',index=False)
            
            await ctx.send(f"Removed from The Fallen: {movie}")
            
        except IndexError:
            await ctx.send("Please run .fallen or .random_fallen command to see list of movies on The Fallen")
            return


    @commands.command(brief='Create a holdover list', description='Create a holdover list for the next week, with movies that have at least 1 vote. NOTE: Add winners to winner list first with winner command')
    async def holdover(self, ctx):

        # Grab rollover time just before writing rollover list
        rollover_time = datetime.utcnow().replace(tzinfo = pytz.utc)

        channel = client.get_channel(CHANNEL_ID) 
        
        holdover_list = []

        async for message in channel.history(after=lastSaturday()):
            if len(message.reactions) > 0 and message.content not in titles:
                holdover_list.append(message.content)
                
        hold_df = pd.DataFrame(sorted(holdover_list), columns = ['Movie'])
        hold_df.to_csv('/home/pi/clumsy-movie-bot/holdover.csv',index=False)
        
        # Write rollover time to an external file      
        time_pd = pd.DataFrame(data = {'Time': [rollover_time]})
        time_pd.to_csv('/home/pi/clumsy-movie-bot/rollover-time.csv', index = False)        
            
        await ctx.send("Holdover list created successfully")
        await ctx.send("Next Week on the Wheel:")        
                
    @commands.command(brief='Print a holdover list', description='Print a list of movies held over from prior weeks. Used when a list of movies is held over for a later date in lieu of special event spins (e.g. Halloween)')
    async def print_holdover(self, ctx):

        global holdover
        
        # Grab rollover time just before writing rollover list
        rollover_time = datetime.utcnow().replace(tzinfo = pytz.utc)        

        # Write rollover time to an external file
        time_pd = pd.DataFrame(data = {'Time': [rollover_time]})
        time_pd.to_csv('/home/pi/clumsy-movie-bot/rollover-time.csv', index = False)    

        await ctx.send("Next Week on the Wheel:")
        
        for movie in list(holdover['Movie']):
            await ctx.send(movie)
            
    @commands.command(brief='Display total running time for all winners', description='Tabulate the total running time among all Clumsy Movie Night winners')
    async def winners_runtime(self, ctx):
        
        global winners
        ia = Cinemagoer()
        runtime = 0
        
        await ctx.send("Tabulating (NOTE: Currently takes about 8-10 minutes due to slow IMDB API)")
        
        for i in range(len(winners)):
            
            try:
                movie = ia.get_movie(winners.iloc[i]['ID'])
                runtime = runtime + int(movie['runtimes'][0])
            except TypeError:
                runtime = runtime + 90
                
        await ctx.send(f"Estimated Runtime: {runtime} minutes")
    
    
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

        plt.savefig("/home/pi/clumsy-movie-bot/discord-images/scorecard.jpg")

        with open('/home/pi/clumsy-movie-bot/discord-images/scorecard.jpg', 'rb') as f:
            file = io.BytesIO(f.read())    

        image = discord.File(file, filename='scorecard.jpg')
        embed = discord.Embed(title = f'Scorecard for {username}')
        embed.set_image(url=f'attachment://scorecard.jpg')

        await ctx.send(file=image, embed=embed)       
        
                
client.add_cog(Voting(client))


###############################################
#               IMDB COMMANDS                 #
###############################################

client.remove_cog('2: IMDB Queries')

class IMDB_Queries(commands.Cog, name='2: IMDB Queries'):
    """Query the IMDB movie database"""

    
    def __init__(self, bot):
        self.bot = bot

        
    @commands.command(brief = 'Run IMDB search for specified title', description = 'Returns the top 10 results from IMDB for using the specified title as the search query')
    async def imdb(self, ctx, *, title: str):
        ia = Cinemagoer()
        global movies
        movies = ia.search_movie(title)
        
        await ctx.send("One moment please...")
        
        results = "Top 10 Search Results from IMDB:\n"

        for i in range(len(movies)):

            results += "[" + str(i+1) + "] " + movies[i]['long imdb title'] + "\n"

            if(i == 9):
                break
                
        await ctx.send(results)


    @commands.command(brief = 'Show IMDB summary for selected movie', description = 'After running .imdb command, use the .imdb_summary <index> command to display the IMDB summary for a selected movie. If the .imdb command has not been run previously, an error message will be produced.')
    async def imdb_summary(self, ctx, index):

        ia = Cinemagoer()

        try:
            global movies
            index = int(index) - 1    
            movieID = movies[index].movieID
            movie = ia.get_movie(movieID)
        except IndexError:
            await ctx.send("Please run .imdb command first to store list of movies")
            return

        
        try:
            title = movie['long imdb title']
        except KeyError:
            title = "Unavailable"

        try:
            description = movie['plot'][0].split('::')[0]
        except KeyError:
            description = "Unavailable"

        try:
            score = str(movie['rating'])
        except KeyError:
            score = "N/A"

        try:
            runtime = str(movie['runtimes'][0]) + " minutes"
        except KeyError:
            runtime = 'N/A'

        embed = discord.Embed(title = title, 
                              description = description,
                             colour = discord.Colour.blue(),
                             url = "https://www.imdb.com/title/tt" + movieID)
        
        embed.add_field(name = 'IMDB Score', value = score, inline = True)
        embed.add_field(name = 'Runtime', value = runtime, inline = True)      

        try:
            embed.set_image(url=movie['full-size cover url'])
        except KeyError:
            pass

        await ctx.send(embed=embed)           

        
    @commands.command(brief='Trivia for past winner', description='Display all IMDB trivia for past winner')
    async def trivia(self, ctx, index:int):
        
        global winners
        
        await ctx.send("Trivia for: " + winners.iloc[index-1]['Title'] + "\n")
        
        movie = Cinemagoer().get_movie(winners.iloc[index-1]['ID'], info=['trivia'])
        trivia = movie['trivia']                               
        
        for fact in trivia:      
            await ctx.send(fact + '\n')

        
        
    @commands.command(brief = 'Select random B-movie from IMDB Top 1000', description = '')
    async def random(self, ctx):

        ia = Cinemagoer()
        global bmovies
        
        try:
            while True:
                index = random.randint(0,len(bmovies)-1)  
                movieID = bmovies[index].movieID
                movie = Cinemagoer().get_movie(movieID)
                exclude = False

                if(movie['kind'] == 'movie' and movie['year'] >= 1950):
                    genres = ['War', 'News', 'Film-Noir', 'History', 'Biography', 'Documentary']
                    for genre in genres:
                        if genre in movie['genres']:
                            exclude = True

                    if exclude == False:
                        break
        except:
            await ctx.send("Something went wrong")
            return

        
        try:
            title = movie['long imdb title']
        except KeyError:
            title = "Unavailable"

        try:
            description = movie['plot'][0].split('::')[0]
        except KeyError:
            description = "Unavailable"

        try:
            score = str(movie['rating'])
        except KeyError:
            score = "N/A"

        try:
            runtime = str(movie['runtimes'][0]) + " minutes"
        except KeyError:
            runtime = 'N/A'

        embed = discord.Embed(title = title, 
                              description = description,
                             colour = discord.Colour.blue(),
                             url = "https://www.imdb.com/title/tt" + movieID)
        
        embed.add_field(name = 'IMDB Score', value = score, inline = True)
        embed.add_field(name = 'Runtime', value = runtime, inline = True)      

        try:
            embed.set_image(url=movie['full-size cover url'])
        except KeyError:
            pass

        await ctx.send(embed=embed)            
        

client.add_cog(IMDB_Queries(client))


###############################################
#               UTILITY COMMANDS              #
###############################################

client.remove_cog('3: Utility')

class Utility(commands.Cog, name='3: Utility'):
    """Helper commands to facilitate testing or manage bot"""

    def __init__(self, bot):
        self.bot = bot
        
        
    @commands.command(brief='Force logout for bot', description='Forces the bot to logoff Discord. Convenience function to interrupt process from jupyter notebook')
    async def kill(self, ctx):
        await ctx.send("Thank you for using Clumsy Movie Bot. Goodbye.")

        # Log bot out of Discord
        await client.logout()

        # Clear internal cache of bot and prepare it to be reopened if necessary
        client.clear()
      
    
    
    # For testing/debugging purposes
    
    @commands.command(brief='Delete all messages', description='Removes last 1000 messages before current datetime (UTC) from test channel')
    async def purge(self, ctx):
        channel = client.get_channel(TEST_ID)

        # Removes the last 1000 messages in channel
        await channel.purge(limit = 1000, before = datetime.utcnow() + timedelta(1))  
        

    @commands.command(brief='Print 5 sample movies', description='Prints 5 seperate messages with a movie name. Reactions should be added to movie title to register vote.')
    async def samples(self, ctx):

        # Create sample movie nominations with emoji reactions to simulate votes

        m1 = await ctx.send("Lair of the White Worm") 
        m2 = await ctx.send("Hausu") 
        m3 = await ctx.send("Hackers") 
        m4 = await ctx.send("Earth Girls are Easy") 
        m5 = await ctx.send("50 Shades Darker") 

        await m1.add_reaction('\U0001f44d')
        await m2.add_reaction('\U0001f44d')
        await m3.add_reaction('\U0001f44d')
        await m4.add_reaction('\U0001f44d')
        await m5.add_reaction('\U0001f44d')

        await m4.add_reaction('\U0001f600')
        await m5.add_reaction('\U0001f600')

        await m4.add_reaction('\U0001f603')
    
    
    
client.add_cog(Utility(client))


# Message bot will print to console when it is connected and ready to receive commands

@client.event
async def on_ready():    
    channel = client.get_channel(TEST_ID)
    ready_msg = f"Ready to comply...\n\nLast Rollover: {lastSaturday()}"
    await channel.send(ready_msg)


client.run(TOKEN)

