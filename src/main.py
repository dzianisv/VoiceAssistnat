#!/usr/bin/env python3

import os
import sys
import logging
import string
from dataclasses import dataclass

import actions
import threading

logger = logging.getLogger("assistant")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stderr))

from hal import detect

hal = detect()
hal.start_blink((1, 2))

from languages import languages

lang_pack = languages[os.getenv("LANGUAGE", "ru")]

logger.info("loading llm...")
from llm_langchains import LLM

logger.info("loading wake word engine...")
import wakeword_pvporcupine as wakeword

llm_type = "openai"
if llm_type == "google":
    llm = LLM(api_key=os.getenv("GOOGLE_API_KEY"))
elif llm_type == "openai":
    llm = LLM(api_key=os.getenv("OPENAI_KEY"))

from stt_speechrecognition import STT

stt = STT(language=lang_pack.google_stt_lang)

tts_type = "google"
if tts_type == "rhvoice":
    from tts_rhvoice import TTS

    tts = TTS()
elif tts_type == "google":
    from tts_gtts import TTS

    tts = TTS()


def speak(text, block=True) -> bool:
    hal.start_blink((0.5, 2))
    try:
        return tts.speak(text, block)
    finally:
        hal.stop_blink()


def listen() -> str:
    hal.led_on()
    try:
        return stt.listen()
    finally:
        hal.led_off()


def wait_for_activation_keyword():
    hal.start_blink((0.5, 10))
    keyword = wakeword.wait()
    logger.debug('recognezed an activation keyword "%s"', keyword)
    communicate()


def communicate():
    text = lang_pack.greeting_message

    while speak(text):
        logger.info("Listening...")
        question = listen()

        if question in languages.stop_words:
            speak(lang_pack.ok)
            break

        if question:
            speak(lang_pack.llm_query, block=False)
            hal.start_blink((0.5, 1))
            text = llm.ask(question)
            logger.info("LLM: %s", text)

            queues = actions.ActionsQueue()

            if actions.run(text, queues):
                action = wakeword.wait()
                queues.down.put(actions.Commands.STOP.value)
                text = lang_pack.greeting_message

                if action == wakeword.KeywordSpottingActions.STOP:
                    break
                elif action == wakeword.KeywordSpottingActions.HEY:
                    continue
        else:
            break

    wait_for_activation_keyword()


if __name__ == "__main__":
    speak(lang_pack.iam_on)
    wait_for_activation_keyword()
