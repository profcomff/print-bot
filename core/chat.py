﻿# Marakulin Andrey @annndruha
# 2021
import os
import logging
import time
import traceback
import requests
import configparser
import psycopg2

import core.answers as ru
import func.vkontakte_functions as vk
import func.database_functions as db
import core.keybords as kb

config = configparser.ConfigParser()
config.read('auth.ini')

PDF_PATH = config["settings"]["pdf_path"]
PRINT_URL = config["print_server"]["print_url"]
GET_MEMBER_URL = config["print_server"]["get_member_url"]


def get_attachments(user):
    if len(user.attachments) > 1:
        vk.write_msg(user.user_id, "Файлов слишком много. Прикрепите только один файл pdf.")
        return
    if user.attachments[0]['type'] != 'doc':
        vk.write_msg(user.user_id, "Я умею печатать только документы в формате pdf.")
        return
    if user.attachments[0]['type'] == 'doc':
        ext = user.attachments[0]['doc']['ext']
        if ext != 'pdf':
            vk.write_msg(user.user_id, "Я умею печатать только документы в формате pdf.")
            return
        title = user.attachments[0]['doc']['title']
        url = user.attachments[0]['doc']['url']

        if not os.path.exists(PDF_PATH):
            os.makedirs(PDF_PATH)
        if not os.path.exists(os.path.join(PDF_PATH, str(user.user_id))):
            os.makedirs(os.path.join(PDF_PATH, str(user.user_id)))

        r = requests.get(url, allow_redirects=True)
        with open(os.path.join(PDF_PATH, str(user.user_id), title), 'wb') as f:
            f.write(r.content)
        vk.write_msg(user.user_id, f"Файл {title} получен.\nПодготовка к печати...")
        return os.path.join(PDF_PATH, str(user.user_id), title), title


def order_print(user, requisites):
    attstatus = get_attachments(user)
    vk_id, surname, number = requisites
    if attstatus is not None:
        pdf_path, title = attstatus
        r = requests.post(PRINT_URL + '/file', json={'surname': surname, 'number': number, 'filename': title})
        if r.status_code == 200:
            pin = r.json()['pin']
            logging.info(pin)

            files = {'file': (title, open(pdf_path, 'rb'), 'application/pdf', {'Expires': '0'})}
            rfile = requests.post(PRINT_URL + '/file/' + pin, files=files)
            if rfile.status_code == 200:
                vk.write_msg(user.user_id, "✔ Файл успешно отправлен на печать.")
            else:
                vk.write_msg(user.user_id, "Ошибка сервера печати. Попробуйте позже.")
        else:
            vk.write_msg(user.user_id, "Ошибка сервера печати. Попробуйте позже.")


def validate_proff(user):
    if len(user.message.split("\n")) == 2:
        surname = user.message.split("\n")[0].strip()
        number = user.message.split("\n")[1].strip()

        r = requests.get(GET_MEMBER_URL, params=dict(surname=surname, v=1, number=number))
        data = db.get_user(user.user_id)
        if r.json() and data is None:
            db.add_user(user.user_id, surname, number)
            kb.auth_button(user.user_id, "Поздравляю! Проверка пройдена и данные сохранёны для этого аккаунта вк. "
                                         "Можете присылать pdf.")
            return True
        elif r.json() and data is not None:
            db.update_user(user.user_id, surname, number)
            kb.auth_button(user.user_id, "Поздравляю! Проверка пройдена и данные обновлены.")
            return True
        elif r.json() is False and data is None:
            vk.write_msg(user.user_id, "Проверка не пройдена. Удостоверьтесь что вы состоите в профкоме и правильно "
                                       "ввели данные.\n\nВведите фамилию и номер профсоюзного билета в формате:")
            vk.write_msg(user.user_id, "Иванов\n1234567")
        elif r.json() is False and data is not None:
            vk.write_msg(user.user_id, "Проверка не пройдена. Удостоверьтесь что вы состоите в профкоме и правильно "
                                       "ввели данные.\n\nВведите фамилию и номер профсоюзного билета в формате:")
            vk.write_msg(user.user_id, "Иванов\n1234567")
    else:
        if db.get_user(user.user_id) is None:
            vk.write_msg(user.user_id, "Введите фамилию и номер профсоюзного билета в формате:")
            vk.write_msg(user.user_id, "Иванов\n1234567")
        else:
            vk.write_msg(user.user_id, "Для того чтобы обновить данные авторизации "
                                       "введите фамилию и номер профсоюзного билета в формате:")
            vk.write_msg(user.user_id, "Иванов\n1234567")


def check_proff(user):
    if db.get_user(user.user_id) is not None:
        vk_id, surname, number = db.get_user(user.user_id)
        r = requests.get(GET_MEMBER_URL, params=dict(surname=surname, number=number, v=1))
        if r.json():
            return vk_id, surname, number
        else:
            vk.write_msg(user.user_id, "Для использования принтера необходимо авторизоваться.\n"
                                       "Введите фамилию и номер профсоюзного билета в формате:")
            vk.write_msg(user.user_id, "Иванов\n1234567")
    else:
        vk.write_msg(user.user_id, "Для использования принтера необходимо авторизоваться.\n"
                                   "Введите фамилию и номер профсоюзного билета в формате:")
        vk.write_msg(user.user_id, "Иванов\n1234567")


def message_analyzer(user):
    try:
        if len(user.message) > 0:
            for word in ru.help_ans.keys():
                if word in user.message.lower():
                    kb.auth_button(user.user_id, ru.help_ans[word])
                    return

        if len(user.message) <= 0 and len(user.attachments) == 0:
            kb.auth_button(user.user_id, ru.kb_ans['help'])
        elif len(user.message) > 0 and len(user.attachments) == 0:
            validate_proff(user)
        elif len(user.message) <= 0 and len(user.attachments) > 0:
            requisites = check_proff(user)
            if requisites is not None:
                order_print(user, requisites)
        elif len(user.message) > 0 and len(user.attachments) > 0:
            requisites = check_proff(user)
            if requisites is not None:
                order_print(user, requisites)

    except OSError as err:
        raise err
    except psycopg2.Error as err:
        vk.write_msg(user.user_id, ru.errors['bd_error'])
        raise err
    except BaseException as err:
        ans = ru.errors['im_broken']
        vk.write_msg(user.user_id, ans)
        logging.error("Unknown Exception (message_analyzer), description:")
        traceback.print_tb(err.__traceback__)
        logging.error(str(err.args))


def process_event(event):
    if event.type == vk.VkBotEventType.MESSAGE_NEW:
        vk_user = vk.user_get(event.message['from_id'])
        user = vk.User(event.message['from_id'], event.message['text'],
                       event.message.attachments, (vk_user[0])['first_name'], (vk_user[0])['last_name'])

        if event.message.payload is not None:
            kb.keyboard_browser(user, event.message.payload)
        else:
            message_analyzer(user)


def chat_loop():
    while True:
        try:
            vk.reconnect()
            for event in vk.longpoll.listen():
                process_event(event)

        except OSError as err:
            logging.error("OSError (longpull_loop), description:")
            traceback.print_tb(err.__traceback__)
            logging.error(str(err.args))
            try:
                logging.warning("Try to recconnect VK...")
                vk.reconnect()
                logging.info("VK connected successful")
                time.sleep(1)
            except:
                logging.error("Recconnect VK failed")
                time.sleep(10)

        except psycopg2.Error as err:
            logging.error("Database Error (longpull_loop), description:")
            traceback.print_tb(err.__traceback__)
            logging.error(err.args)
            try:
                logging.error("Try to recconnect database...")
                db.reconnect()
                logging.error("Database connected successful")
                time.sleep(1)
            except:
                logging.error("Recconnect database failed")
                time.sleep(10)

        except BaseException as err:
            logging.error("BaseException (longpull_loop), description:")
            traceback.print_tb(err.__traceback__)
            logging.error(str(err.args))
            time.sleep(5)

        except:
            logging.error("Something go wrong. (chat_loop)")
