# Ported more or less from hubot's "wunderground" script
import asyncio
from datetime import datetime
import json
import os
import re
import urllib.parse

import aiohttp

from dywypi.event import Message
from dywypi.plugin import Plugin


plugin = Plugin('wunderground')

@plugin.command('textweather')
def textweather(event):
    # TODO strip me/at/for/in/...
    location = event.argstr or '94103'

    data = yield from get_data_or_reply(event, location, 'forecast')
    if data:
        report = data['forecast']['txt_forecast']['forecastday'][0]
        yield from event.reply(
            "{title} in {location}: {report.fcttext} ({ttl})".format(
                title=report['title'],
                location=location,
                fcttext=report['fcttext'],
                ttl=ttl(data),
            )
        )


@plugin.command('weather')
def weather(event):
    # TODO strip me/at/for/in/...
    location = event.argstr or '94103'

    weather_data = yield from get_data_or_reply(event, location, 'forecast')
    if weather_data:
        yield from event.reply(send_simple_forecast(weather_data))


# TODO the rest of these require URL shortening which i'm too lazy to port atm
'''
# weather me <location> - short-term forecast
#
# radar me <location> - recent radar image
#
# satellite me <location> - get a recent satellite image
#
# weathercam me <location> - get a weather webcam image near location
#
# location can be zip code, ICAO/IATA airport code, state/city (CA/San_Franciso).

  robot.respond /radar\s?(me|at|for|in)? ?(.*)$/i, (msg) ->
    location = msg.match[2] or "94103"
    get_data robot, msg, location, 'radar', location.replace(/\s/g, '_'), send_radar, 60*10

  robot.respond /satellite\s?(me|at|for|in)? ?(.*)$/i, (msg) ->
    location = msg.match[2] or "94103"
    get_data robot, msg, location, 'satellite', location.replace(/\s/g, '_'), send_satellite, 60*10

  robot.respond /weathercam\s?(me|at|for|in)? ?(.*)$/i, (msg) ->
    location = msg.match[2] or "94103"
    get_data robot, msg, location, 'webcams', location.replace(/\s/g, '_'), send_webcam, 60*30
'''

@plugin.command('almanac')
def almanac(event):
    location = event.argstr or '94103'

    data = yield from get_data_or_reply(event, location, 'almanac')
    if not data:
        return

    low = data['almanac']['temp_low']
    high = data['almanac']['temp_high']
    yield from event.reply(
        "Normal: {normal_low}F-{normal_high}F"
        " | Record Low: {record_low}F in {record_low_year}"
        " | Record High: {record_high}F in {record_high_year}"
        .format(
            normal_low=low['normal']['F'],
            normal_high=high['normal']['F'],
            record_low=low['record']['F'],
            record_low_year=low['recordyear'],
            record_high=high['record']['F'],
            record_high_year=high['recordyear'],
        )
    )


@plugin.command('astronomy')
def astronomy(event):
    location = event.argstr or '94103'

    data = yield from get_data_or_reply(event, location, 'astronomy')
    if not data:
        return

    current = data['moon_phase']['current_time']
    sunrise = data['moon_phase']['sunrise']
    sunset = data['moon_phase']['sunset']

    yield from event.reply(
        "Current time: {now_hour}:{now_minute}"
        "  Sunrise: {rise_hour}:{rise_minute}"
        "  Sunset: {set_hour}:{set_minute}"
        .format(
            now_hour=current['hour'],
            now_minute=current['minute'],
            rise_hour=sunrise['hour'],
            rise_minute=sunrise['minute'],
            set_hour=sunset['hour'],
            set_minute=sunset['minute'],
        )
    )


@asyncio.coroutine
def get_data_or_reply(event, location, service):
    # TODO hubot stores this in redis; if we ever have such a thing it should
    # surely be pluggable and more explicit than this is
    cache = event.data.setdefault('cache', {})
    try:
        data = yield from get_data(cache, location, service, location, 60*60*2)
    except NoAPIKey:
        yield from event.reply("HUBOT_WUNDERGROUND_API_KEY is not set. Sign up at http://www.wunderground.com/weather/api/.")
    except AmbiguousLocation as exc:
        alts, = exc.args
        yield from event.reply("Possible matches for '{location}': {matches}".format(location=location, matches=', '.join(alts)))
    except ServerReportedError as exc:
        message, = exc.args
        yield from event.reply(message)
    else:
        return data


@asyncio.coroutine
def get_data(cache, location, service, query, lifetime, recursed=False):
    # TODO what?  redis??
    # redis key to use
    cache_key = key_for(service, location)

    data = cache.get(cache_key)
    if data:
        if ttl(data) > 0:
            # Cache is valid
            return data
        else:
            del cache[cache_key]

    # TODO what about interleaved responses?  cache should contain a "pending"
    # thing perhaps?

    api_key = os.environ['HUBOT_WUNDERGROUND_API_KEY']
    if not api_key:
        raise NoAPIKey

    # get new data
    url = "http://api.wunderground.com/api/{key}/{service}/q/{query}.json".format(
        key=api_key,
        service=service,
        query=urllib.parse.quote(underscore(query)),
    )
    response = yield from aiohttp.request('GET', url)
    # TODO check for a non-200 response. cache it for some short amount of time && send 'unavailable'

    # TODO why the hell does aiohttp not decode the response for me
    data = json.loads((yield from response.read()).decode('utf8'))
    if 'error' in data['response']:
        # Probably an unknown place
        raise ServerReportedError(data['response']['error']['description'])

    elif 'results' in data['response']:
        # Ambiguous place, multiple matches
        alts = [alternative_place(item) for key, item in data['response']['results'].items()]
        alts = [item for item in alts if item]
        # If there's only 1 place, let's just get it.
        # Also, guard against infinite recursion.
        if len(alts) == 1 and not recursed:
            return get_data(cache, location, service, alts[0], lifetime, recursed=True)
        else:
            raise AmbiguousLocation(alts)

    else:
        # Looks good
        data['retrieved'] = datetime.now()
        data['lifetime'] = lifetime
        cache[cache_key] = data
        return data


def send_simple_forecast(data):
    weather_icons = dict(
        clear='☀',
        sunny='☀',
        chance='☁',
        flurries='☁',
        fog='☁',
        hazy='☁',
        cloudy='☁',
        sleet='☂',
        rain='☂',
        snow='☂',
        tstorms='☂',
    )

    report = data['forecast']['simpleforecast']['forecastday']
    parts = []
    for day in report:
        icon = '?'
        for term, possible_icon in weather_icons.items():
            if term in day['icon']:
                icon = possible_icon
                break

        parts.append("{weekday}: {icon} {low}F–{high}F".format(
            weekday=day['date']['weekday_short'],
            icon=icon,
            low=day['low']['fahrenheit'],
            high=day['high']['fahrenheit'],
        ))

    return ' | '.join(parts)


'''

send_radar = (msg, location, data) ->
  url_shortener(msg, "#{data.radar.image_url}#.png")

send_satellite = (msg, location, data) ->
  url_shortener(msg, "#{data.satellite.image_url}#.png")

send_webcam = (msg, location, data) ->
  cam = msg.random data.webcams
  if cam?
    msg.send "#{cam.handle} in #{cam.city}, #{cam.state} (#{formatted_ttl data})"
    url_shortener(msg, "#{cam.CURRENTIMAGEURL}#.png")
  else
    msg.send "No webcams near #{location}. (#{formatted_ttl data})"

'''


# quick normalization to reduce caching of redundant data
def key_for(service, query):
    return "{}-{}".format(service, query.lower())


# how long till our cached data expires?
def ttl(data):
    lifetime = data.get('lifetime')
    retrieved = data.get('retrieved')
    if not lifetime or not retrieved:
        return -1

    return lifetime - (datetime.utcnow() - retrieved).total_seconds()


def alternative_place(item):
    if item['country'] != 'US' or not item['state'] or not item['city']:
        return ''

    return "{}/{}".format(item['state'], item['city'])


def underscore(string):
    return re.sub(r'\s', '_', string)


'''
url_shortener = (msg, url) ->
    msg
        .http("http://api.bitly.com/v3/shorten")
        .query
            login: process.env.HUBOT_BITLY_USERNAME
            apiKey: process.env.HUBOT_BITLY_API_KEY
            longUrl: url
            format: "json"
        .get() (err, res, body) ->
            response = JSON.parse body
            msg.send if response.status_code is 200 then response.data.url else response.status_txt
'''


class NoAPIKey(Exception):
    pass


class AmbiguousLocation(Exception):
    pass


class ServerReportedError(Exception):
    pass
