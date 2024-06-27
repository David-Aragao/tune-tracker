import spotipy
from spotipy.oauth2 import SpotifyOAuth 
import os
import dotenv
import requests
import json
from time import time
from base64 import b64encode
from flask import Flask, request, url_for, session, redirect, render_template, jsonify

# Loads .env file contaning the cliene id and secret
dotenv.load_dotenv()
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")

# Redirect URI defined in spotify API project
redirect_uri = 'http://localhost:5000/callback'
# Scope that is going to be used to read the top items of the user
scope = ['user-top-read', 'playlist-modify-public', 'playlist-modify-private', 'user-read-private']


app = Flask(__name__)

# Sets thet cookies that will contain the token of the session
app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
app.secret_key = 'ASds949#$RSSDQS1asd#'
TOKEN_INFO = 'token_info'

@app.route('/')
def login():
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    session.clear()
    # The following three lines will format the token in the way required by the API
    auth_string = client_id + ":" + client_secret
    auth_bits = auth_string.encode("utf-8")
    auth_base64 = str(b64encode(auth_bits), "utf-8")

    # Gets the code from the URL
    code = request.args.get('code')

    url = "https://accounts.spotify.com/api/token"

    headers = {
        "Authorization": "Basic " + auth_base64,
        "Content-Type": "application/x-www-form-urlencoded" 
    }

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
        }
    
    # Retrieves the return value of the Post method, which if sucessful will return the access token
    result = requests.post(url, headers=headers, data=data)
    token_info = json.loads(result.content)

    # Saves the token into the session cookies 
    session[TOKEN_INFO] = token_info
    return redirect(url_for('home'))

@app.route('/home')
def home():

    token_info = get_token()
    token = token_info['access_token']

    headers = {
        "Authorization": "Bearer " + token
    }

    arts_url = f"https://api.spotify.com/v1/me/top/artists?time_range=short_term&offset=0&limit=10"
    tracks_url = f"https://api.spotify.com/v1/me/top/tracks?time_range=short_term&offset=0&limit=10"
    
    top_artists = requests.get(arts_url, headers=headers)
    top_tracks = requests.get(tracks_url, headers=headers)

    if top_artists.status_code != 200 or top_tracks.status_code != 200:
        return "Failed to retrieve data", 500

    json_artists = json.loads(top_artists.content)
    json_tracks = json.loads(top_tracks.content)

    # Gets top 10 listened artists in the last 4 weeks

    
    artist_data = [
        (item['name'], item['external_urls']['spotify'], item['images'][0]['url'])
        for item in json_artists['items']
    ]
    
    artist_data_list = list(artist_data)

    first_artist = artist_data_list[0]

    # Gets top 10 listened tracks in the last 4 weeks
    tracks_data = [
        (item['name'], item['external_urls']['spotify'], item['album']['images'][0]['url'], item['uri'])
        for item in json_tracks['items']
    ]
    
    tracks_data_list = list(tracks_data)
    
    session['tracks'] = tracks_data_list
    session['time_range'] = '4 Weeks'
    

    first_track = tracks_data_list[0]

    return render_template('top_items.html', artist_data_list=artist_data_list, tracks_data_list=tracks_data_list, first_artist=first_artist, first_track=first_track)
   

@app.route('/top_items/<time_range>')
def get_top_items(time_range):
    
    token_info = get_token()
    token = token_info['access_token']

    headers = {
        "Authorization": "Bearer " + token
    }

    arts_url = f"https://api.spotify.com/v1/me/top/artists?time_range={time_range}&offset=0&limit=10"
    tracks_url = f"https://api.spotify.com/v1/me/top/tracks?time_range={time_range}&offset=0&limit=10"

    if time_range == 'short_term':
        time_span = '4 Weeks'
    elif time_range == 'medium_term':
        time_span = 'Month'
    else:
        time_span = 'Year'

    top_artists = requests.get(arts_url, headers=headers)
    top_tracks = requests.get(tracks_url, headers=headers)

    if top_artists.status_code != 200 or top_tracks.status_code != 200:
        return "Failed to retrieve data", 500

    json_artists = json.loads(top_artists.content)
    json_tracks = json.loads(top_tracks.content)

    # Gets top 10 listened artists in the specific time range

    
    artist_data = [
        (item['name'], item['external_urls']['spotify'], item['images'][0]['url'])
        for item in json_artists['items']
    ]
    
    artist_data_list = list(artist_data)

    first_artist = artist_data_list[0]

    # Gets top 10 listened tracks in the specific time range
    tracks_data = [
        (item['name'], item['external_urls']['spotify'], item['album']['images'][0]['url'], item['uri'])
        for item in json_tracks['items']
    ]
    
    tracks_data_list = list(tracks_data)

    session['tracks'] = tracks_data_list
    session['time_range'] = time_span

    first_track = tracks_data_list[0]

    print(session['tracks'])
    
    return render_template('top_items_partial.html', artist_data_list=artist_data_list, tracks_data_list=tracks_data_list, first_artist=first_artist, first_track=first_track, time_span=time_span)


# Creates the playlist
@app.route('/playlist')
def create_playlist():
    token_info = get_token()

    # Ensure token_info is not an error message.
    if isinstance(token_info, str):  
        return jsonify({"error": token_info}), 401
    
    token = token_info['access_token']
    user_id = get_user_id()


    time_range = session['time_range']
    tracks = session['tracks']


    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
    }

    data = {
        "name": f"Top Tracks - Last {time_range}",
        "description": f"Your favourite tracks in the last {time_range}",
        "public": True
    }

    data = json.dumps(data)

    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"

    result = requests.post(url, headers=headers, data=data) 
    json_result = json.loads(result.content)



    # HTTP 201 means "Created"
    if result.status_code != 201:  
        return jsonify({"error": "Failed to create playlist"}), 500

    playlist_id = json_result['id']
    position = 0

    if not playlist_id:
        return jsonify({"error": "Error retrieving playlist ID"}), 500

    for track in tracks:
        uri = track[3]
        add_item_to_playlist(playlist_id, uri, position)
        position = position + 1


    return jsonify({"message": "Playlist created successfully"})


def add_item_to_playlist(playlist_id, uri, position):
    token_info = get_token()
    token = token_info['access_token']

    

    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"

    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
    }

    data = {
        "uris": [uri],
        "position": position
    }

    data = json.dumps(data)

    result = requests.post(url, headers=headers, data=data)
    json_result = json.loads(result.content)


    return 0


def get_user_id():
    token_info = get_token()
    token = token_info['access_token']

    headers = {
        "Authorization": "Bearer " + token
    }

    url = "https://api.spotify.com/v1/me"

    result = requests.get(url, headers=headers)

    json_result = json.loads(result.content)

    user_id = json_result['id']

    return user_id


@app.route('/logout')
def logout():
    session.pop(TOKEN_INFO, None)
    return render_template('login.html')

            
    
def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        return redirect(url_for('login', external=False))
    
    now = int(time())
    expires_at = token_info['expires_in'] + now

    is_expired = expires_at <= now

    if is_expired:
        spotify_oauth = create_spotify_oauth()
        token_info = spotify_oauth.refresh_access_token(token_info['refresh_token'])
    
    return token_info


# Initializes the authorization of the user
def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=client_id, 
        client_secret=client_secret,
        scope=scope, 
        redirect_uri=redirect_uri
    )
    
if __name__ == '__main__':
    app.run(debug=True)