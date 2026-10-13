## UPDATE: Setup for Raspberry Pi
Clone the github repo within your home directory
```bash
git clone https://github.com/alipphardt/clumsy-movie-bot.git
```

## Environmental Variables
Within the clumsy-movie-bot directory, create a .env file and add the following environmental variables
```bash
DISCORD_BOT_TOKEN='REPLACE_WITH_TOKEN'
DISCORD_MOVIES_CHANNEL='REPLACE_WITH_CHANNEL_NUM'
DISCORD_TERMINAL_CHANNEL='REPLACE_WITH_CHANNEL_NUM'
DISCORD_TEST_CHANNEL='REPLACE_WITH_CHANNEL_NUM'
WHEEL_API_KEY='REPLACE_WITH_KEY'
TMDB_TOKEN='REPLACE_WITH_TOKEN'
```
Where to find these values:
- DISCORD_BOT_TOKEN: This is the Client Secret provided when creating the OAuth2 permissions at https://discord.com/developers/applications
- DISCORD_MOVIES_CHANNEL: In this setup, this is the channel dedicated to movie nominations and supports rollover and holdover based commands. To find the channel ID in Discord, go to Settings > Advanced and enable Developer Mode. Once this is enabled you can right click on the channel name and select COPY CHANNEL ID to send to your clipboard.
- DISCORD_TERMINAL_CHANNEL: In this setup, this is a channel separate from movie nominations that is intended solely for issuing commands to the bot for sending votes to the wheel, tallying, or any TMDB based commands. 
- DISCORD_TEST_CHANNEL: In this setup, this is a channel that is intended solely for the purpose of testing the bot prior to deployment. Supports some utility commands that are not available elsewhere.
- WHEEL_API_KEY: This API key may be obtained by creating an account on https://wheelofnames.com/api-doc
- TMDB_TOKEN: This token may be obtained by registering for a Developer API Token through The Movie Database (TMDB). See [TMDB - Getting Started](https://developer.themoviedb.org/docs/getting-started)

## Python Dependencies (Older Raspberry Pi Models)
Install third party libraries into system environment
```bash
pip3 install --upgrade -r requirements.txt
```

## Python Dependencies (Newer Models)
Newer models protect the system environment. It is recommended that you create a virtual environment for python library installs. From the clumsy-movie-bot directory, run the following commands:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

## Creating the Service
From the clumsy-movie-bot directory, copy the clumsy-movie-bot.service file to your /lib/systemd/system folder. This will allow the app to be run on system boot
```bash
sudo cp clumsy-movie-bot.service /lib/systemd/system
```

Run the following command to enable the new service
```bash
sudo systemctl daemon-reload
sudo systemctl enable clumsy-movie-bot.service
sudo systemctl start clumsy-movie-bot.service
```

## Background

Saturday night movies via Discord have been a guilty pleasure among friends during quarantine, starting with well known cult films such as [The Room](https://www.imdb.com/title/tt0368226/) or [Miami Connection](https://www.imdb.com/title/tt0092549/) and delving more into the weird over time. As the selection of movies have broadened its come to be known as 'Clumsy' Movie Night, a term that was coined by my daughter.

Nominations and voting take place on a dedicated Discord text channel, with movie titles submitted as messages and votes submitted through reactions or emojis. In the early days of clumsy movie night, there may have been up to 10 movies at at a time where votes were tallied in an Excel sheet before being populated into a wheel for random selection ([wheelofnames.com](https://wheelofnames.com)). Number of entries on the wheel for a given movie are equal to the number of votes received. The first movie to be selected three times is chosen as the movie to be shown that night.

![Sample votes in Discord channel](/images/samples.png)

![Wheel populated with sample movie titles](/images/wheelofnames.png)

Eventually as more members were added to the Discord channel nominations increased to up to 50 movie titles in a given week, which became unsustainable for manual tallies. Enter the Clumsy Movie Bot, whose likeness was pulled from the killer robot in the 1990 sci-fi thriller, [Hardware](https://www.imdb.com/title/tt0099740)

![Robot from 1990 movie Hardware](/images/hardware-robot.jpg)

## Implementation with Python

The bot is developed in Python and primarily uses **discord.py** for Discord commands, **pandas** for CSV-backed state, **matplotlib/seaborn** for charts, [Wheel of Names](https://wheelofnames.com) for weighted random selection, and [TMDB](https://www.themoviedb.org/) for movie search/summary data.

The commands for the bot are broken into three main categories:

1. Voting/wheel commands facilitate vote tallying based on reactions/emojis, submitting weighted movie lists to [wheelofnames.com](https://wheelofnames.com), printing a manual fallback list when the Wheel of Names API is unavailable, helper commands for adding winning movies to temporary or permanent lists, and creating rollover or holdover title lists for future weeks.
2. TMDB commands integrate with themoviedb.org to run searches for specified titles against the TMDB database. Results returned may be used to add movies into a permanent list of winners, to select movies from the Top 1000 b-movies at random, or to show a movie summary.
3. Utility/social commands support testing and movie-night operations. This includes generating sample nominations in the test channel, generating BINGO cards, purging Wheel of Names wheels associated with the API key, and forcing the bot to logout.

The bot is intended to run persistently, for example on a Raspberry Pi using the included systemd service file.

All commands are implemented through python decorator functions from the **discord.py** commands extension, with a custom check to ensure that commands are only accepted from configured testing or production Discord channels.

## Current Features

Current bot features include:

- `.tally` vote chart generation
- `.votecount` total vote counting
- `.moviecount` nomination counting since the last rollover
- `.oldest` oldest currently nominated movies by first appearance in channel history
- `.wheel` weighted Wheel of Names submission with Discord fallback output on API failure
- `.wheel_fallen` Wheel of Names submission for The Fallen list
- `.wheel_purge` deletion of Wheel of Names wheels associated with the configured API key
- `.exclude`, `.winner`, `.exclude_list`, and `.winner_clear` winner-management helpers
- `.rollover`, `.holdover`, and `.print_holdover` weekly nomination lifecycle helpers
- `.fallen`, `.random_fallen`, and `.remove_fallen` Fallen-list helpers
- `.winners` previous-winner listing
- `.tmdb` and `.tmdb_summary` TMDB search/summary helpers
- `.random` random B-movie lookup through TMDB
- `.bingo` custom movie-night BINGO card generation
- `.samples` test nomination generation from the terminal channel into the test channel

## Sample Commands

The following are sample outputs from several of the basic commands.

The **.tally** command tallies all votes that occurred since the previous rollover of movie nominations, creates a Matplotlib/Seaborn bar chart of the votes, and then submits the message to the current channel attaching the plot as an embedded image. If there are no votes since the last rollover, the bot reports that no votes were found instead of attempting to render an empty chart.

![Tally of sample votes](/images/tally.png)

The **.wheel** command takes the list of vote tallies, duplicates each title according to the number of votes received, and submits the weighted list to Wheel of Names using the current v3 API. If the API request fails, the bot automatically prints the weighted list to Discord so it can be copied into Wheel of Names manually. Titles containing terms known to be rejected by Wheel of Names are sanitized for the submitted wheel by replacing vowels with asterisks; the original nomination text is not changed.

![List of movie titles proportional to number of votes](/images/wheel.png)

The **.moviecount** command counts movie nomination messages since the last rollover. It counts nominations whether or not they have votes, including bot-generated rollover nominations, and excludes the rollover header message `Next Week on the Wheel:`.

The **.oldest** command finds the 10 oldest currently nominated movies by scanning channel history for the first appearance of each title. It excludes known bot/control messages and stops scanning history once all current titles have been found.

The **.wheel_fallen** command submits The Fallen list to Wheel of Names. It uses the same Wheel of Names v3 payload and title-sanitization behavior as `.wheel`.

The **.bingo** command generates a custom 5x5 movie-night BINGO card as a PNG image.

The **.winners** command prints a list of all movies previously selected on Clumsy Movie Night. The titles have associated numbers which may be used with the IMDB trivia command (deprecated 1/26/2026).

![List of prior winners](/images/winners.png)

Searches on TMDB may also be performed using the **.tmdb** command. Given that multiple movies may be returned with similar names, the default behavior is to return a list of numbered options.

![TMDB query for the Matrix](/images/imdb.png)

Running a followup command **.tmdb_summary** with the specified index will display a TMDB summary with the title, description, release date, running time, and movie poster.

![TMDB summary for The Matrix](/images/imdb_summary.png)

Finally, a random movie by bot selection is also available to provide an additional level of chaos. By running the **.random** command, a random movie is selected from the local Top 1000 b-movies list and looked up in TMDB.

![Random movie from TMDB](/images/random.png)


## Creating the bot account on Discord

In order to create a dedicated account for the bot, login to Discord via [https://discord.com/developers/applications](https://discord.com/developers/applications). Under **General Information**, create a new application specifying a name, description, and app icon for the application. Then go to the menu labelled **Bot** and select to Add Bot. This will convert the application to an account that may connect to Discord similar to a regular user. 

In order to add the bot as an accepted user to a given channel, the server admin must accept an invite that may be sent in the form of an OAuth2 URL. This URL can be created by going to the **OAuth2** menu, selecting 'Bot' from the list of Scopes and then assigning the following permissions:

![Screenshot of scope for bot](/images/scope.png)

![Screenshot of permissions for bot](/images/permissions.png)

Once all of the desired permissions have been set, the admin accesses the OAuth2 URL and accepts the invite, allowing the bot access with the specified permissions to the Discord channel. 

Running the python script or Jupyter notebook will then initialize the bot with the custom commands and connects it to Discord. From there the bot is ready to receive commands from any user in the channel.

## Considerations and Next Steps

The bot can be run persistently from a Raspberry Pi using the setup described above. For safer live operation, useful future command additions would include a general `.status` command, a `.preview_wheel` command, and a `.preview_rollover` command so major actions can be reviewed before mutating files or submitting to external services.

Another area of focus is exploratory analysis of movies selected using available movie metadata. Findings may be used to inform the development of an improved recommender system that will suggest movies similar to titles chosen in the past, rather than simply selecting randomly from a top 1000 list.

For example, a quick analyses of keywords for all prior winners shows that the majority of movies have keywords associated with cult-film, psychotronic-film, or surrealism. Using top keywords as selected features might provide a means to generate a training set for supervised machine learning, allowing the bot to select new movies that meet a combination of keyword criteria. This could also be coupled with numeric scores based on how much the audience enjoyed each given movie, which could be implemented with some custom scoring commands.

![Word cloud of top keywords for winning movies](/images/imdb-keywords-word-cloud.png)

The imdbpy package also has utility functions to download the latest version of the IMDB database for local SQL queries. This could be used to develop more complex queries than what is capable from the imdbpy API. For example, select all movies where the lead actor served as writer and director (e.g. Tommy Wiseau in The Room).

![Tommy Wiseau](/images/the-room.gif)
