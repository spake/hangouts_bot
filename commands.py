import sys, json, random, asyncio

import hangups
import re
import random
from urllib.request  import urlopen
from hangups.ui.utils import get_conv_name
import dice
from hangupsbot.utils import text_to_segments


class CommandDispatcher(object):
    """Register commands and run them"""
    def __init__(self):
        self.commands = {}
        self.unknown_command = None

    @asyncio.coroutine
    def run(self, bot, event, *args, **kwds):
        """Run command"""
        try:
            func = self.commands[args[0]]
        except KeyError:
            if self.unknown_command:
                func = self.unknown_command
            else:
                raise

        # Automatically wrap command function in coroutine
        # (so we don't have to write @asyncio.coroutine decorator before every command function)
        func = asyncio.coroutine(func)

        args = list(args[1:])

        try:
            yield from func(bot, event, *args, **kwds)
        except Exception as e:
            print(e)

    def register(self, func):
        """Decorator for registering command"""
        self.commands[func.__name__] = func
        return func

    def register_unknown(self, func):
        """Decorator for registering unknown command"""
        self.unknown_command = func
        return func

# CommandDispatcher singleton
command = CommandDispatcher()


@command.register_unknown
def unknown_command(bot, event, *args):
    """Unknown command handler"""
    bot.send_message(event.conv,
                     '{}: u wot m8? That command doesnt exist!'.format(event.user.full_name))


@command.register
def help(bot, event, cmd=None, *args):
    """Help me, Obi-Wan Kenobi. You're my only hope."""
    if not cmd:
        segments = [hangups.ChatMessageSegment('Supported Commands:', is_bold=True),
                    hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK),
                    hangups.ChatMessageSegment(', '.join(sorted(command.commands.keys())))]
    else:
        try:
            command_fn = command.commands[cmd]
            segments = [hangups.ChatMessageSegment('{}:'.format(cmd), is_bold=True),
                        hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK)]
            segments.extend(text_to_segments(command_fn.__doc__))
        except KeyError:
            yield from command.unknown_command(bot, event)
            return

    bot.send_message_segments(event.conv, segments)


@command.register
def ping(bot, event, *args):
    """Zahrajem si ping pong!"""
    bot.send_message(event.conv, 'pong')

@command.register
def socs(bot, event, *args):
    url = "http://issocsopen.com/api"
    page = urlopen(url)
    bot.send_message(event.conv, page.read().decode('utf-8'))


@command.register
def echo(bot, event, *args):
    """Pojďme se opičit!"""
    bot.send_message(event.conv, '{}'.format(' '.join(args)))

@command.register
def roll(bot, event, diceroll, *args):
    if diceroll < 50:
        r = dice.roll(diceroll)
        output = ""
        for i in r:
            output += " " + str(i)
        output += "] = " + str(int(r))
        bot.send_message(event.conv, "[" + output.strip())
    else:
        bot.send_message(event.conv, "u wob m8? trying to fuk me up?")

@command.register
def users(bot, event, *args):
    """Výpis všech uživatelů v aktuálním Hangoutu (včetně G+ účtů a emailů)"""
    segments = [hangups.ChatMessageSegment('People in this channel ({}):'.format(len(event.conv.users)),
                                           is_bold=True),
                hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK)]
    for u in sorted(event.conv.users, key=lambda x: x.full_name.split()[-1]):
        link = 'https://plus.google.com/u/0/{}/about'.format(u.id_.chat_id)
        segments.append(hangups.ChatMessageSegment(u.full_name, hangups.SegmentType.LINK,
                                                   link_target=link))
        if u.emails:
            segments.append(hangups.ChatMessageSegment(' ('))
            segments.append(hangups.ChatMessageSegment(u.emails[0], hangups.SegmentType.LINK,
                                                       link_target='mailto:{}'.format(u.emails[0])))
            segments.append(hangups.ChatMessageSegment(')'))
        segments.append(hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK))
    bot.send_message_segments(event.conv, segments)


@command.register
def user(bot, event, username, *args):
    """Vyhledá uživatele podle jména"""
    username_lower = username.strip().lower()
    segments = [hangups.ChatMessageSegment('Searching users for "{}":'.format(username),
                                           is_bold=True),
                hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK)]
    for u in sorted(bot._user_list._user_dict.values(), key=lambda x: x.full_name.split()[-1]):
        if not username_lower in u.full_name.lower():
            continue

        link = 'https://plus.google.com/u/0/{}/about'.format(u.id_.chat_id)
        segments.append(hangups.ChatMessageSegment(u.full_name, hangups.SegmentType.LINK,
                                                   link_target=link))
        if u.emails:
            segments.append(hangups.ChatMessageSegment(' ('))
            segments.append(hangups.ChatMessageSegment(u.emails[0], hangups.SegmentType.LINK,
                                                       link_target='mailto:{}'.format(u.emails[0])))
            segments.append(hangups.ChatMessageSegment(')'))
        segments.append(hangups.ChatMessageSegment(' ... {}'.format(u.id_.chat_id)))
        segments.append(hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK))
    bot.send_message_segments(event.conv, segments)


@command.register
def hangouts(bot, event, *args):
    """Výpis všech aktivních Hangoutů, v kterých řádí bot
        Vysvětlivky: c ... commands, f ... forwarding, a ... autoreplies"""
    segments = [hangups.ChatMessageSegment('List of active hangouts:', is_bold=True),
                hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK)]
    for c in bot.list_conversations():
        s = '{} [c: {:d}, f: {:d}, a: {:d}]'.format(get_conv_name(c, truncate=True),
                                                    bot.get_config_suboption(c.id_, 'commands_enabled'),
                                                    bot.get_config_suboption(c.id_, 'forwarding_enabled'),
                                                    bot.get_config_suboption(c.id_, 'autoreplies_enabled'))
        segments.append(hangups.ChatMessageSegment(s))
        segments.append(hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK))

    bot.send_message_segments(event.conv, segments)


@command.register
def rename(bot, event, *args):
    """Přejmenuje aktuální Hangout"""
    yield from bot._client.setchatname(event.conv_id, ' '.join(args))


@command.register
def leave(bot, event, *args):
    """Opustí aktuální Hangout"""
    yield from event.conv.send_message([
        hangups.ChatMessageSegment('I\'ll be back!')
    ])
    yield from bot._conv_list.delete_conversation(event.conv_id)


@command.register
def easteregg(bot, event, easteregg, eggcount=1, period=0.5, *args):
    """Spustí combo velikonočních vajíček (parametry: vajíčko [počet] [perioda])
       Podporovaná velikonoční vajíčka: ponies, pitchforks, bikeshed, shydino"""
    for i in range(int(eggcount)):
        yield from bot._client.sendeasteregg(event.conv_id, easteregg)
        if int(eggcount) > 1:
            yield from asyncio.sleep(float(period) + random.uniform(-0.1, 0.1))

@command.register
def spoof(bot, event, *args):
    """Spoofne instanci IngressBota na určené koordináty"""
    segments = [hangups.ChatMessageSegment('!!! CAUTION !!!', is_bold=True),
                hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK)]
    segments.append(hangups.ChatMessageSegment('User {} ('.format(event.user.full_name)))
    link = 'https://plus.google.com/u/0/{}/about'.format(event.user.id_.chat_id)
    segments.append(hangups.ChatMessageSegment(link, hangups.SegmentType.LINK,
                                               link_target=link))
    segments.append(hangups.ChatMessageSegment(')has been reported to the NSA for spoofing!'))
    bot.send_message_segments(event.conv, segments)


@command.register
def reload(bot, event, *args):
    """Znovu načte konfiguraci bota ze souboru"""
    bot.config.load()


@command.register
def quit(bot, event, *args):
    """Nech bota žít!"""
    print('HangupsBot killed by user {} from conversation {}'.format(event.user.full_name,
                                                                     get_conv_name(event.conv, truncate=True)))
    yield from bot._client.disconnect()


@command.register
def config(bot, event, cmd=None, *args):
    """Zobrazí nebo upraví konfiguraci bota
        Parametry: /bot config [get|set] [key] [subkey] [...] [value]"""

    if cmd == 'get' or cmd is None:
        config_args = list(args)
        value = bot.config.get_by_path(config_args) if config_args else dict(bot.config)
    elif cmd == 'set':
        config_args = list(args[:-1])
        if len(args) >= 2:
            bot.config.set_by_path(config_args, json.loads(args[-1]))
            bot.config.save()
            value = bot.config.get_by_path(config_args)
        else:
            yield from command.unknown_command(bot, event)
            return
    else:
        yield from command.unknown_command(bot, event)
        return

    if value is None:
        value = 'Parameter does not exist!'

    config_path = ' '.join(k for k in ['config'] + config_args)
    segments = [hangups.ChatMessageSegment('{}:'.format(config_path),
                                           is_bold=True),
                hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK)]
    segments.extend(text_to_segments(json.dumps(value, indent=2, sort_keys=True)))
    bot.send_message_segments(event.conv, segments)

@command.register
def flip(bot, event, *args):
    """Flip a coin"""
    n = random.randint(0, 1)
    bot.send_message(event.conv, "Heads" if n else "Tails")

@command.register
def prereqs(bot, event, code, *args):
    """Print the prereqs for a course"""
    try:
        course_info = json.loads(urlopen('http://pathways.csesoc.unsw.edu.au/tree/'+code.upper()).read().decode('utf-8'))
        if course_info['below']:
            for prereq in course_info['below']:
                if prereq['exists']:
                    bot.send_message(event.conv, prereq['code'] + ' ' + prereq['name'])
        else:
            bot.send_message(event.conv, 'No prerequisites')
    except:
        bot.send_message(event.conv, 'something wobbed up')

@command.register
def fortune(bot, event, *args):
    """Give a random fortune"""
    url = "http://www.fortunecookiemessage.com"
    html = urlopen(url).read().decode('utf-8')
    m = re.search("class=\"cookie-link\">(<p>)?", html)
    m = re.search("(</p>)?</a>",html[m.end():])
    bot.send_message(event.conv, m.string[:m.start()])

@command.register
def define(bot, event, *args):
    text = ''.join(args)
    if len(text) < 50:
        url = 'http://www.igrec.ca/project-files/wikparser/wikparser.php?word={}&query=def&count=1'.format(text)
        html = urlopen(url).read().decode('utf-8')
        if html != "No such word." and html != "No such word for specified language." and html:
            bot.send_message(event.conv, html)
        else:
            url = "http://urbanscraper.herokuapp.com/define/{}".format(text)
            msg = json.loads(urlopen(url).read().decode('utf-8'))["definition"]
            if msg:
                bot.send_message(event.conv, msg)
            else:
                bot.send_message(event.conv, '... disappointed')
    else:
        bot.send_message(event.conv, 'too long m8')

@command.register
def acrostic(bot, event, *args):
    words = open('/usr/share/dict/words').read().strip().split()
    for arg in args:
        letters = [letter for letter in arg]
        random_words = []
        for letter in letters:
            if letter == letters[-1]:
                random_words.append(random.choice([word for word in words if word[0].lower() == letter and word[len(word)-2] != "'"]))
            else:
                random_words.append(random.choice([word for word in words if word[0].lower() == letter]))
        
        random_words = " ".join([word[0].upper() + word[1:] for word in random_words])
        
        msg = "".join([letter.upper() for letter in letters]) + ": " + random_words
        bot.send_message(event.conv, msg)
