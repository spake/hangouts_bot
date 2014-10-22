import logging, shlex, unicodedata, asyncio, re, json

import hangups

from hangupsbot.commands import command
from urllib.request import urlopen


class MessageHandler(object):
    """Handle Hangups conversation events"""

    def __init__(self, bot, bot_command='/wob'):
        self.bot = bot
        self.bot_command = bot_command

    @staticmethod
    def word_in_text(word, text):
        """Return True if word is in text"""
        # Transliterate unicode characters to ASCII and make everything lowercase
        word = unicodedata.normalize('NFKD', word).encode('ascii', 'ignore').decode().lower()
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()

        # Replace delimiters in text with whitespace
        for delim in '.,:;!?':
            text = text.replace(delim, ' ')

        return True if word in text.split() else False

    @asyncio.coroutine
    def handle(self, event):
        """Handle conversation event"""
        if logging.root.level == logging.DEBUG:
            event.print_debug()

        if not event.user.is_self and event.text:
            if event.text.split()[0].lower() == self.bot_command:
                # Run command
                yield from self.handle_command(event)
            else:
                # Forward messages
                yield from self.handle_forward(event)

                # Send automatic replies
                yield from self.handle_autoreply(event)
                
                # I AM TYPING IN CAPSLOCK
                yield from self.handle_capslock(event)
                
                # thanks wobcke. thobcke
                yield from self.handle_thanks(event)

                yield from self.handle_regex(event)

    @asyncio.coroutine
    def handle_command(self, event):
        """Handle command messages"""
        # Test if command handling is enabled
        if not self.bot.get_config_suboption(event.conv_id, 'commands_enabled'):
            return

        # Parse message
        line_args = shlex.split(event.text, posix=False)

        # Test if command length is sufficient
        if len(line_args) < 2:
            self.bot.send_message(event.conv,
                                  '{}: u wot m8? Your command is the wrong length.'.format(event.user.full_name))
            return

        # Test if user has permissions for running command
        commands_admin_list = self.bot.get_config_suboption(event.conv_id, 'commands_admin')
        if commands_admin_list and line_args[1].lower() in commands_admin_list:
            admins_list = self.bot.get_config_suboption(event.conv_id, 'admins')
            if event.user_id.chat_id not in admins_list:
                self.bot.send_message(event.conv,
                                      '{}: u wot m8? You don\'t have permission for that.'.format(event.user.full_name))
                return

        # Run command
        yield from command.run(self.bot, event, *line_args[1:])

    @asyncio.coroutine
    def handle_forward(self, event):
        """Handle message forwarding"""
        # Test if message forwarding is enabled
        if not self.bot.get_config_suboption(event.conv_id, 'forwarding_enabled'):
            return

        forward_to_list = self.bot.get_config_suboption(event.conv_id, 'forward_to')
        if forward_to_list:
            for dst in forward_to_list:
                try:
                    conv = self.bot._conv_list.get(dst)
                except KeyError:
                    continue

                # Prepend forwarded message with name of sender
                link = 'https://plus.google.com/u/0/{}/about'.format(event.user_id.chat_id)
                segments = [hangups.ChatMessageSegment(event.user.full_name, hangups.SegmentType.LINK,
                                                       link_target=link, is_bold=True),
                            hangups.ChatMessageSegment(': ', is_bold=True)]
                # Copy original message segments
                segments.extend(event.conv_event.segments)
                # Append links to attachments (G+ photos) to forwarded message
                if event.conv_event.attachments:
                    segments.append(hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK))
                    segments.extend([hangups.ChatMessageSegment(link, hangups.SegmentType.LINK, link_target=link)
                                     for link in event.conv_event.attachments])
                self.bot.send_message_segments(conv, segments)

    @asyncio.coroutine
    def handle_autoreply(self, event):
        """Handle autoreplies to keywords in messages"""
        # Test if autoreplies are enabled
        if not self.bot.get_config_suboption(event.conv_id, 'autoreplies_enabled'):
            return

        autoreplies_list = self.bot.get_config_suboption(event.conv_id, 'autoreplies')
        if autoreplies_list:
            for kwds, sentence in autoreplies_list:
                for kw in kwds:
                    if self.word_in_text(kw, event.text):
                        self.bot.send_message(event.conv, sentence)
                        break
    
    @asyncio.coroutine
    def handle_capslock(self, event):
        """Handle capslock"""
        message = re.sub(r'[^a-zA-Z]', '', event.text)
        if (message and message == message.upper()):
            self.bot.send_message(event.conv, "YOU ARE TYPING IN CAPSLOCK!")

    @asyncio.coroutine
    def handle_thanks(self, event):
        text = event.text.strip()
        m = re.match(r'^thanks[, ]+(.*)$', text, re.I)
        if m:
            subject = m.group(1).lower()
            subject = re.sub(r'^(y|[^aeiouy]+|)', 'th', subject)
            self.bot.send_message(event.conv, subject)

    last_message = {}
    last_message_lock = asyncio.Lock()

    @asyncio.coroutine
    def handle_regex(self, event):
        with (yield from self.last_message_lock):
            text = event.text
            user_id = event.user_id

            if text.lower().startswith('s/') and len(text) > 2:
                try:
                    STATE_PATTERN = 0
                    STATE_REPL = 1
                    STATE_FLAGS = 2

                    state = STATE_PATTERN
                    i = 2

                    s = ''
                    ALLOWED_FLAGS = {'g', 'i'}
                    flags = set()

                    while i < len(text):
                        curr = text[i]
                        next_ = text[i+1] if i+1 < len(text) else None

                        if state == STATE_PATTERN or state == STATE_REPL:
                            if curr == '\\':
                                if next_ == '/':
                                    s += next_
                                else:
                                    s += curr + next_
                                i += 2
                            elif curr == '/':
                                if state == STATE_PATTERN:
                                    pattern = s
                                elif state == STATE_REPL:
                                    repl = s
                                
                                state += 1
                                s = ''
                                i += 1
                            else:
                                s += curr
                                i += 1
                        elif state == STATE_FLAGS:
                            if curr not in ALLOWED_FLAGS:
                                raise Exception()
                            flags.add(curr)
                            i += 1

                    if user_id in self.last_message:
                        msg = self.last_message[user_id]

                        re_flags = 0
                        if 'i' in flags:
                            re_flags |= re.I

                        if 'g' in flags:
                            msg = re.sub(pattern, repl, msg, flags=re_flags)
                        else:
                            msg = re.sub(pattern, repl, msg, count=1, flags=re_flags)

                        self.last_message[user_id] = msg

                        self.bot.send_message(event.conv, '"{}" FTFY'.format(msg))
                except Exception as e:
                    pass
                    #self.bot.send_message(event.conv, 'pooped: ' + repr(e))
                    self.bot.send_message(event.conv, 'm8, l2regex')
            else:
                self.last_message[user_id] = text
