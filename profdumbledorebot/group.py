#!/usr/bin/python
# -*- coding: utf-8 -*-

############################################################################
#                                                                          #
# Profesor Dumbledore Bot                                                  # 
# Copyright (C) 2019 - Pikaping                                            #
#                                                                          #
# This program is free software: you can redistribute it and/or modify     #
# it under the terms of the GNU Affero General Public License as           #
# published by the Free Software Foundation, either version 3 of the       #
# License, or (at your option) any later version.                          #
#                                                                          #
# This program is distributed in the hope that it will be useful,          #
# but WITHOUT ANY WARRANTY; without even the implied warranty of           #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            #
# GNU Affero General Public License for more details.                      #
#                                                                          #
# You should have received a copy of the GNU Affero General Public License #
# along with this program.  If not, see <https://www.gnu.org/licenses/>.   #
#                                                                          #
############################################################################

import os
import re
import time
import logging
import telegram
from threading import Thread
from Levenshtein import distance

from nursejoybot.config import get_config
from telegram.ext.dispatcher import run_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from nursejoybot.welcome import send_welcome


@run_async
def joined_chat(bot, update, job_queue):
    logging.debug("%s %s", bot, update)
    chat_id, chat_type, user_id, text, message = extract_update_info(update)
    new_chat_member = message.new_chat_members[0] if message.new_chat_members else None

    config = get_config()
    bot_alias = config['telegram']['botalias']

    if new_chat_member.username == bot_alias:
        if are_banned(user_id, chat_id):
            bot.leaveChat(chat_id=chat_id)
            return

        chat_title = message.chat.title
        chat_id = message.chat.id
        group = get_group(chat_id)
        if group is None:
            set_group(chat_id, message.chat.title)

        message_text = (
            "Si necesitais ayuda podéis lanzar chispas rojas c"
            "on vuestra varita o utilizando el comando `/help`"
            " para conocer todas las funciones. Aseguraos de v"
            "er la ayuda para prefectos de los grupos, donde s"
            "e explica en detalle todos los pasos que se deben"
            " seguir.".format(ensure_escaped(chat_title)))
        bot.sendMessage(
            chat_id=chat_id, 
            text=message_text, 
            parse_mode=telegram.ParseMode.MARKDOWN)

    elif new_chat_member.username != bot_alias:
        chat_id = message.chat.id
        user_id = update.effective_message.new_chat_members[0].id

        group = get_join_settings(chat_id)
        if group is not None:
            if group.silence:
                delete_message(chat_id, message.message_id, bot)

            if are_banned(user_id, user_id):
                bot.kickChatMember(chat_id, user_id)
                good_luck(bot, update, "Banned")
                return

            user = get_user(user_id)       
            if user is None and group.validationrequired is not ValidationRequiered.NO_VALIDATION:
                bot.kickChatMember(chat_id=chat_id, user_id=user_id, until_date=time.time()+31)
                if group.mute is False:
                    output = "👌 Entrenador sin registrarse expulsado!"
                    bot.sendMessage(
                        chat_id=chat_id, 
                        text=output, 
                        parse_mode=telegram.ParseMode.MARKDOWN)
                good_luck(bot, update, "Not registered")
                return

            if group.validationrequired is ValidationRequiered.VALIDATION and user.validation_type is ValidationType.NONE:
                bot.kickChatMember(chat_id=chat_id, user_id=user_id, until_date=time.time()+31)
                if group.mute is False:
                    output = "👌 Entrenador sin validarse expulsado!"
                    bot.sendMessage(
                        chat_id=chat_id, 
                        text=output, 
                        parse_mode=telegram.ParseMode.MARKDOWN)           
                good_luck(bot, update, "Not registered")
                try:
                    bot.sendMessage(
                        chat_id=user_id, 
                        text="❌ Debes validarte para entrar en este grupo", 
                        parse_mode=telegram.ParseMode.MARKDOWN)
                except Exception:
                    pass
                return
        
            if group.max_members is not None and group.max_members > 0 and bot.get_chat_members_count(chat_id) >= group.max_members:
                if group.mute is False:
                    output = "❌ El número máximo de integrantes en el grupo ha sido alcanzado"
                    sent = bot.sendMessage(
                        chat_id=chat_id, 
                        text=output, 
                        parse_mode=telegram.ParseMode.MARKDOWN)
                    delete_object = DeleteContext(chat_id, sent.message_id)
                    job_queue.run_once(
                        callback_delete, 
                        10,
                        context=delete_object
                    )
                time.sleep(2)
                bot.kickChatMember(chat_id=chat_id, user_id=user_id, until_date=time.time()+31)
                return

            if (not exists_user_group(user_id, chat_id)):
                set_user_group(user_id, chat_id)
            else:
                join_group(user_id, chat_id, False)

            logging.debug("HAS RULES %s", has_rules(chat_id))
            if has_rules(chat_id):
                bot.restrict_chat_member(
                    chat_id,
                    user_id,
                    until_date=0,
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False
                )

            if get_welc_pref(chat_id):
                sent = send_welcome(bot, update)
                if sent is not None and group.delete_cooldown is not None and group.delete_cooldown > 0:
                    delete_object = DeleteContext(chat_id, sent.message_id)
                    job_queue.run_once(
                        callback_delete, 
                        group.delete_cooldown,
                        context=delete_object
                    )

            if group.joy and (user is None or user.level is None):
                sent_message = alert_joy(bot, chat_id, user_id)
                if sent_message is not None:
                    delete_object = DeleteContext(chat_id, sent_message.message_id)
                    job_queue.run_once(
                        callback_delete, 
                        30,
                        context=delete_object
                    )
            
            ladmin = get_particular_admin(chat_id)
            if ladmin is not None and ladmin.welcome:
                admin = get_admin_from_linked(chat_id)
                if admin is not None and admin.welcome is True:
                    replace_pogo = replace(user_id, message.from_user.first_name)
                    message_text = ("ℹ️ {}\n👤 {} ha entrado en el grupo").format(message.chat.title, replace_pogo)
                    bot.sendMessage(chat_id=admin.id, text=message_text,
                                    parse_mode=telegram.ParseMode.MARKDOWN)

        else:
            logging.info("CREATING GROUP")
            set_group(chat_id, message.chat.title)

            message_text = (
                "Entrenadores de *{}*, sed bienvenidos al Centro P"
                "okémon de la región de Telegram.\nAntes de poder "
                "utilizarme, un administrador tiene que configurar"
                " algunas cosas. Comenzad viendo la ayuda con el c"
                "omando `/help` para conocer todas las funciones. "
                "Aseguraos de ver la *ayuda para administradores*,"
                " donde se explica en detalle todos los pasos que "
                "se deben seguir.\n\n <Si este mensaje ha aparecido"
                "y no has promocionado el grupo a supergrupo, pide "
                "ayuda en @enfermerajoyayuda >".format(ensure_escaped(chat_title))
            )
            bot.sendMessage(
                chat_id=chat_id, 
                text=message_text, 
                parse_mode=telegram.ParseMode.MARKDOWN)


@run_async
def process_group_message(bot, update):
    chat_id, chat_type, user_id, text, message = extract_update_info(update)
    msg = update.effective_message
    
    if are_banned(user_id, chat_id):
        return
  
    group = get_group(chat_id)
    if group is None:
        set_group(chat_id, message.chat.title)
        logging.debug("GROUP created")
    if (not exists_user_group(user_id, chat_id)):
        set_user_group(user_id, chat_id)
        logging.debug("USER GROUP created")
        
    message_counter(user_id, chat_id)
    if text is None or msg.photo is None:
        if msg and msg.document:
            process_gif(bot, update)
            return
        elif msg and msg.contact:
            process_contact(bot, update)
            return
        elif msg and msg.game:
            process_game(bot, update)
            return
        elif msg and msg.location or msg.venue:
            process_ubi(bot, update)
            return
        elif msg and msg.photo:
            process_pic(bot, update)
            return
        elif msg and msg.sticker:
            process_sticker(bot, update)
            return
        elif msg and msg.voice or msg.audio:
            process_voice(bot, update)
            return
        elif msg and msg.video or msg.video_note:
            process_video(bot, update)
            return

    if msg and msg.entities and process_url(bot, update):
        return

    if nanny_text(bot, user_id, chat_id, message):
        return

    if text is not None and re.search("@admin(?!\w)", text) is not None:
        replace_pogo = replace(user_id, message.from_user.first_name)
        message_text=("ℹ️ {}\n👤 {} ha enviado una alerta a los administradores\n\nMensaje: {}").format(
            message.chat.title,
            replace_pogo,
            text
        )
        for admin in bot.get_chat_administrators(chat_id):
            user = get_user(admin.user.id)
            if user is not None and user.adm_alerts:
                bot.sendMessage(
                    chat_id=admin.user.id,
                    text=message_text,
                    parse_mode=telegram.ParseMode.MARKDOWN
                )
        ladmin = get_particular_admin(chat_id)
        if ladmin is not None and ladmin.admin:
            admin = get_admin_from_linked(chat_id)
            if admin is not None and admin.admin is True:
                bot.sendMessage(
                    chat_id=admin.id,
                    text=message_text,
                    parse_mode=telegram.ParseMode.MARKDOWN
                )
                return

    if text and len(text) < 31:
        commands = get_commands(chat_id)
        if commands is None:
            return
        for command in commands:
            logging.debug("%s %s", text, command)
            if distance(text.lower(), command.command.lower()) < 1:
                logging.debug("%s %s", text, command.command)
                ENUM_FUNC_MAP = {
                    Types.TEXT.value: bot.sendMessage,
                    Types.BUTTON_TEXT.value: bot.sendMessage,
                    Types.STICKER.value: bot.sendSticker,
                    Types.DOCUMENT.value: bot.sendDocument,
                    Types.PHOTO.value: bot.sendPhoto,
                    Types.AUDIO.value: bot.sendAudio,
                    Types.VOICE.value: bot.sendVoice,
                    Types.VIDEO.value: bot.sendVideo
                }
                if command.command_type != Types.TEXT and command.command_type != Types.BUTTON_TEXT:
                    ENUM_FUNC_MAP[command.command_type](chat_id, command.media)
                    return

                if command.command_type == Types.BUTTON_TEXT:
                    buttons = get_cmd_buttons(chat_id)
                    keyb = build_keyboard(buttons)
                    keyboard = InlineKeyboardMarkup(keyb)
                else:
                    keyboard = None
                try:
                    msg = update.effective_message.reply_text(
                        command.media,
                        reply_markup=keyboard,
                        parse_mode=telegram.ParseMode.MARKDOWN,
                        disable_web_page_preview=True, 
                        disable_notification=False
                        )

                except IndexError:
                    msg = update.effective_message.reply_text(
                            markdown_parser(
                                "\nBip bop bip: El mensaje tiene errores de"
                                "Markdown, revisalo y configuralo de nuevo."),
                        parse_mode=telegram.ParseMode.MARKDOWN)
                except KeyError:
                    msg = update.effective_message.reply_text(
                            markdown_parser(
                                "\nBip bop bip: El mensaje tiene errores con"
                                "las llaves, revisalo y configuralo de nuevo."),
                        parse_mode=telegram.ParseMode.MARKDOWN)
                return


def alert_joy(bot, chat_id, user_id):
    button_list = [[
        InlineKeyboardButton(text="Empezar!", url="https://t.me/NurseJoyBot")
    ]]
    reply_markup = InlineKeyboardMarkup(button_list)
    sent_message = bot.send_message(
        chat_id=chat_id,
        text=(
            "¡Hola entrenador/a!\n\nPara permanecer en este grupo, debes registra"
            "rte conmigo: @NurseJoyBot.\nPara hacerlo, pulsa *Empezar*, inicia el"
            " chat privado y escríbeme `/register`.\n\n👉 Siguiendo esos sencillo"
            "s pasos estarás validado/a."
        ),
        parse_mode=telegram.ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return sent_message


