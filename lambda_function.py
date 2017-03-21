# -*- coding: utf-8 -*-

from __future__ import print_function
from pyicloud import PyiCloudService
from base64 import b64decode
import boto3
import os

APPLICATION_ID = boto3.client('kms').decrypt(CiphertextBlob=b64decode(os.environ['APPLICATION_ID']))['Plaintext']
APPLE_ID = boto3.client('kms').decrypt(CiphertextBlob=b64decode(os.environ['APPLE_ID']))['Plaintext']
APPLE_PASSWORD = boto3.client('kms').decrypt(CiphertextBlob=b64decode(os.environ['APPLE_PASSWORD']))['Plaintext']

# --------------- Helpers that build all of the responses ----------------------

def build_speechlet_response(title, output, reprompt_text, should_end_session):
    return {
        'outputSpeech': {
            'type': 'PlainText',
            'text': output
        },
        'card': {
            'type': 'Simple',
            'title': "SessionSpeechlet - " + title,
            'content': "SessionSpeechlet - " + output
        },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        },
        'shouldEndSession': should_end_session
    }


def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }


# --------------- Functions that control the skill's behavior ------------------

def get_help_response(intent, session):
    session_attributes = session['attributes']
    card_title = "Help"
    speech_output = "I will find your Apple device.Say 'List devices'"
    reprompt_text = session_attributes
    should_end_session = False

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def done_response(target_device):
    session_attributes = {}
    card_title = "Done"
    speech_output = "%s will sound soon" % target_device[1]
    reprompt_text = None
    should_end_session = True

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def no_device_response():
    session_attributes = {}
    card_title = "Done"
    speech_output = "No device on your account."
    reprompt_text = None
    should_end_session = True

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def select_device_response(intent, session):
    devices = get_devices(session)
    session_attributes = {'devices': devices}
    card_title = "Select your device"
    speech_output = "Tell me which device do you want to find"
    for (index, device) in enumerate(devices):
        speech_output += ", %s is Number %i, " %(device[1], index)
    reprompt_text = speech_output
    should_end_session = False

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def handle_session_end_request():
    session_attributes = {}
    card_title = "Session Ended"
    speech_output = "Have a nice day! "
    should_end_session = True
    reprompt_text = None

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def get_devices(session):
    if session.get('attributes', {}) and "devices" in session.get('attributes', {}):
        devices = session['attributes']['devices']
    else:
        api = PyiCloudService(APPLE_ID, APPLE_PASSWORD)
        devices = []
        for (id, device) in api.devices.items():
            devices.append((id, str(device)))

    if len(devices) == 0:
        return no_device_response()
    else:
        return devices


def play_device(intent, session):
    devices = get_devices(session)
    target_device = None

    if intent is None and 'TARGET_DEVICE_NAME' in os.environ:
        candidate_devices = [d for d in devices if d[1] == os.environ['TARGET_DEVICE_NAME']]
        if len(candidate_devices) > 0:
            target_device = candidate_devices[0]
    elif 'TargetDeviceNumber' in intent['slots']:
        target_index = int(intent['slots']['TargetDeviceNumber']['value'])
        if target_index >= 0 and target_index < len(devices):
            target_device = devices[target_index]

    if target_device is None:
        return select_device_response(intent, session)
    else:
        api = PyiCloudService(APPLE_ID, APPLE_PASSWORD)
        api.devices[target_device[0]].play_sound()
        return done_response(target_device)


# --------------- Events ------------------

def on_session_started(session_started_request, session):
    """ Called when the session starts """

    print("on_session_started requestId=" + session_started_request['requestId']
          + ", sessionId=" + session['sessionId'])


def on_launch(launch_request, session):
    """ Called when the user launches the skill without specifying what they
    want
    """
    print("on_launch requestId=" + launch_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    # 探すデバイスが環境変数で指定されている場合は、いきなり鳴らす
    # 指定がない場合はデバイスのリストを返す
    if 'TARGET_DEVICE_NAME' in os.environ:
        return play_device(None, session)
    else:
        return select_device_response(None, session)


def on_intent(intent_request, session):
    """ Called when the user specifies an intent for this skill """

    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    # Dispatch to your skill's intent handlers
    if intent_name == "TargetDeviceIsIntent":
        return play_device(intent, session)
    elif intent_name == "ListMyDevicesIntent":
        return select_device_response(intent, session)
    elif intent_name == "AMAZON.HelpIntent":
        return get_help_response(intent, session)
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":
        return handle_session_end_request()
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    """ Called when the user ends the session.

    Is not called when the skill returns should_end_session=true
    """
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # add cleanup logic here


# --------------- Main handler ------------------

def lambda_handler(event, context):
    """ Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """
    print("event.session.application.applicationId=" +
          event['session']['application']['applicationId'])

    """
    Prevent someone else from configuring a skill that sends requests to this
    function.
    """
    if (event['session']['application']['applicationId'] != APPLICATION_ID):
        raise ValueError("Invalid Application ID")

    if event['session']['new']:
        on_session_started({'requestId': event['request']['requestId']},
                           event['session'])

    if event['request']['type'] == "LaunchRequest":
        return on_launch(event['request'], event['session'])
    elif event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'])
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])
