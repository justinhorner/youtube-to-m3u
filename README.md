# youtube-to-m3u
Play YouTube live streams in any player

# Known Issues <br>
The streamlink plugin is currently getting 400 errors - For now use the non streamlink script as I have fixed this. I will look at a custom streamlink plugin if streamlink do not fix it themselve

## Important Note
The m3u/extracted m3u8 links will only work on machines that have the same public IP address (on the same local network) as the machine that extracted them. To play on a client that has a different public IP (on a different network) use a non flask version and load the m3u into a m3u proxy such as threadfin to restream

## Choose script option
youtube-live.py - Uses a flask server to automatically pull the actuall stream link. Server needs to be running all the time for m3u to work. Best for always working stream<br>
<br>
youtube-non-server.py - Pulls stream link into m3u but script will have to manually run (or cron job) every few hours as the stream links will expire <br>
<br>
youtube_non_stream_link.py - Same as youtube-non-server.py but doesn't require streamlink - only use if you are unable to install streamlink as if anything changes youtube side the script will need updating instead of just updating streamlink

## Requirements
### All Versions
python - must be 3.10 or higher (3.8 or lower is not supported by streamlink) <br>
requests (can be installed by typing ```pip install requests``` at cmd/terminal window) <br>

### All Versions except youtube_non_stream_link.py
install [streamlink](https://streamlink.github.io/install.html) and make it available at path

### youtube-live.py only <br>
flask (can be installed by typing ```pip install flask``` at cmd/terminal window) <br>
youtubelive.m3u

### youtube-non-server.py and youtube_non_stream_link.py<br>
youtubelinks.xml

## Verify streamlink install
To test streamlink install type in a new cmd/terminal window
```
streamlink --version
```
The output should be
streamlink "version number" eg 8.1.2 <br>
If it says unknown command/'streamlink' is not recognized as an internal or external command,
operable program or batch file. <br>
Then you need to make sure you have installed streamlink to path/environmental variables

## How To Use youtube-live.py
Open youtubelive.m3u <br>
Change the ip address in the streamlink to the ip address of the machine running the script <br>
You can also change the port but if you do this you must change the port to match at the bottom of youtube-live.py <br>
<br>
To add other live streams just add into m3u in the following format 

```
#EXTINF:-1 tvg-name="Channel Name" tvg-id="24.7.Dummy.us" tvg-logo="https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/YouTube_dark_logo_2017.svg/2560px-YouTube_dark_logo_2017.svg.png" group-title="YouTube",Channel Name
http://192.168.1.123:6095/stream?url=https://www.youtube.com/@ChannelName/live
```

Or if the channel has multiple live streams you can use the /watch? link however these links will change if the channel stops and restarts broadcast <br>
<br>
You can change tvg-name tvg-logo group-title and channel name and if you want to link to an epg change tvg-id to match your epgs tvg-id for that channel <br>
(The two sample streams link to the epg from epgshare01.online UK and USA epgs) <br>
<br>
Run the python script <br>
python youtube-live.py or python3 youtube-live.py if you have the old python2 installed <br>
<br>
Script must be running for the m3u to work

## How To Use youtube-non-server.py or youtube_non_stream_link.py
Open youtubelinks.xml in a code text editor eg notepad++ <br>
Add in your channel details for your youtube stream in the following format

```
<channel>
        <channel-name>ABC News</channel-name>
        <tvg-id>ABCNEWS.us</tvg-id>
        <tvg-name>ABC News</tvg-name>
        <tvg-logo>https://github.com/tv-logo/tv-logos/blob/main/countries/united-states/abc-news-light-us.png?raw=true</tvg-logo>
        <group-title>News</group-title>
        <youtube-url>https://www.youtube.com/@abcnews/live</youtube-url>
    </channel>
```

channel-name = name of channel <br>
tvg-id = epg tag which matches tvg-id in your epg (you can enter anything here if you don't have an epg or leave blank) <br>
tvg-name = name of channel <br>
tvg-logo = direct link to channel logo png <br>
group-title = group you want channel to appear in <br>
youtube-url = url to youtube live stream - can be @channelname/live or /watch? <br>
<br>
Run the python script <br>
python youtube-non-server.py or python3 youtube-non-server.py if you have the old python2 installed <br>
<br>
As the stream links will expire you will need to setup a cron job/scheduled task or manually run the script every few hours <br>
To have the stream urls automatically be pulled use the flask version <br>
<br>
