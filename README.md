## UPDATE: Setup for Raspberry Pi
Clone the github repo within your home directory
```bash
git clone https://github.com/alipphardt/clumsy-movie-bot.git
```

Open the .bashrc file within your home directory and add the following environmental variables
```bash
export DISCORD_BOT_TOKEN='REPLACE_WITH_TOKEN'
export DISCORD_MOVIES_CHANNEL=<REPLACE_WITH_CHANNEL_NUM>
export DISCORD_TERMINAL_CHANNEL=<REPLACE_WITH_CHANNEL_NUM>
export DISCORD_TEST_CHANNEL=<REPLACE_WITH_CHANNEL_NUM>
export WHEEL_API_KEY='REPLACE_WITH_KEY'
```

Run the following command to load environmental variables
```bash
source .bashrc
```

Install third party libraries
```bash
pip3 install --upgrade -r /home/pi/clumsy-movie-bot/requirements.txt
```

Copy the clumsy-movie-bot.service file to your /lib/systemd/system folder. This will allow the app to be run on system boot
```bash
sudo cp /home/pi/clumsy-movie-bot/clumsy-movie-bot.service /lib/systemd/system
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

The bot was developed in Python and primarily uses two libraries for its commands, the **discordpy** and **cinemagoer** (previously imdbpy) libraries.

The commands for the bot are broken into three main categories:

1. Voting/wheel commands facilitate the tallying of votes based on reactions/emojis, printing a list of movie titles to be copy/pasted into [wheelofnames.com](https://wheelofnames.com), helper commands for adding winning movies to temporary or permanent lists, as well as the ability to create a list of rollover titles for the following week for movies not in the winners list.
2. IMDB commands integrate with IMDB.com to run searches for specified titles against the IMDB database. Results returned may be used to add movies into a permanent list of winners, to select movies from the Top 1000 b-movies at random, or to generate trivia for the current winning movie.
3. Utility commands are used strictly in testing/development. This includes generating sample movie titles with votes, the ability to purge messages from the testing channel, and a user command to force the bot to logout.

For the purposes of documentation, the python scripts are managed in a Jupyter notebook and run from a local laptop, with future plans to run from a Raspberry Pi in order to keep the bot available around the clock.

All commands are implemented through the use of python decorator functions to extend the command function in the Commands class of the **discordpy** library, with a custom check implemented to ensure that commands are only accepted from specific channels in the testing or production Discord servers.

## Sample Commands

The following are sample outputs from several of the basic commands.

The **.tally** command tallys all votes that occurred since the previous rollover of movie nominations (typically Saturday at 10 PM), creates and saves a Matplotlib bar chart of the votes, and then submits the message to the current channel attaching the plot as an embedded image.

![Tally of sample votes](/images/tally.png)

The **.wheel** command takes the list of vote tallies and prints the titles multiple times according to the number of votes received. This provides a list that is easy for the user to copy and paste into the wheel before spinning.

![List of movie titles proportional to number of votes](/images/wheel.png)

The **.winners** command prints a list of all movies previously selected on Clumsy Movie Night. The titles have associated numbers which may be used with the IMDB trivia command.

![List of prior winners](/images/winners.png)

By issuing the **.trivia** command with the specified index, the bot will pull top 10 trivia for the winning movie from IMDB and print the results to the current channel.

![Sample trivia for The Room](/images/trivia.png)

Searches on IMDB may also be performed using the **.imdb** command. Given that multiple movies may be returned with similar names, the default behavior is to return a list of numbered options.

![IMDB query for the Matrix](/images/imdb.png)

Running a followup command **.imdb_summary** with the specified index will display an IMDB summary with the title, description, IMDB score, running time, and movie poster.

![IMDB summary for The Matrix](/images/imdb_summary.png)

Finally, a random movie by bot selection is also available to provide an additional level of chaos. By running the **.random** command, a random movie is selected from the Top 1000 movies on IMDB with keyword b-movie.

![Random movie from IMDB](/images/random.png)


## Creating the bot account on Discord

In order to create a dedicated account for the bot, login to Discord via [https://discord.com/developers/applications](https://discord.com/developers/applications). Under **General Information**, create a new application specifying a name, description, and app icon for the application. Then go to the menu labelled **Bot** and select to Add Bot. This will convert the application to an account that may connect to Discord similar to a regular user. 

In order to add the bot as an accepted user to a given channel, the server admin must accept an invite that may be sent in the form of an OAuth2 URL. This URL can be created by going to the **OAuth2** menu, selecting 'Bot' from the list of Scopes and then assigning the following permissions:

![Screenshot of scope for bot](/images/scope.png)

![Screenshot of permissions for bot](/images/permissions.png)

Once all of the desired permissions have been set, the admin accesses the OAuth2 URL and accepts the invite, allowing the bot access with the specified permissions to the Discord channel. 

Running the python script or Jupyter notebook will then initialize the bot with the custom commands and connects it to Discord. From there the bot is ready to receive commands from any user in the channel.

## Considerations and Next Steps

The downside to the current setup is that scripts running from a local laptop may be interrupted when the machine is shutdown, disconnecting the bot from the server. Therefore, next steps are to run the bot from a local server that retains a persistent connection to the Discord server. This can be setup through a Raspberry Pi. Additional options are third party services such as Heroku apps that run your application remotely. This will require some modifications as the current script is set up to pull access tokens, channel IDs, and so forth from environmental variables on the local computer.

Another area of focus is some exploratory analyses of movies selected using IMDB database information. Findings may be used to inform the development of an improved recommender system that will suggest movies similar to titles chosen in the past, rather than simply selecting randomly from a top 1000 list.

For example, a quick analyses of keywords for all prior winners shows that the majority of movies have keywords associated with cult-film, psychotronic-film, or surrealism. Using top keywords as selected features might provide a means to generate a training set for supervised machine learning, allowing the bot to select new movies that meet a combination of keyword criteria. This could also be coupled with numeric scores based on how much the audience enjoyed each given movie, which could be implemented with some custom scoring commands.

![Word cloud of top keywords for winning movies](/images/imdb-keywords-word-cloud.png)

The imdbpy package also has utility functions to download the latest version of the IMDB database for local SQL queries. This could be used to develop more complex queries than what is capable from the imdbpy API. For example, select all movies where the lead actor served as writer and director (e.g. Tommy Wiseau in The Room).

![Tommy Wiseau](/images/the-room.gif)
