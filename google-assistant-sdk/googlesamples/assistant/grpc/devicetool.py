# Copyright (C) 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Sample that implements device registration for the Google Assistant API."""

import json
import logging
import os

import click
import google.oauth2.credentials
import google.auth.transport.requests


def failed_request_exception(message, r):
    """Build ClickException from a failed request."""
    try:
        resp = json.loads(r.text)
        message = '%s: %d %s' % (message,
                                 resp['error']['code'],
                                 resp['error']['message'])
        if 'details' in resp['error']:
            details = '\n'.join(d['detail'] for d in resp['error']['details'])
            message += ' ' + details
        return click.ClickException(message)
    except ValueError:
        # fallback on raw text response if error is not structured.
        return click.ClickException('%s: %d\n%s' % (message,
                                                    r.status_code,
                                                    r.text))


# Prints out a device model in the terminal by parsing dict
def pretty_print_model(devicemodel):
    PRETTY_PRINT_MODEL = """Device Model Id: %(deviceModelId)s
        Project Id: %(projectId)s
        Device Type: %(deviceType)s"""
    logging.info(PRETTY_PRINT_MODEL % devicemodel)
    for trait in devicemodel['traits']:
        logging.info('        Trait %s' % trait)
    logging.info('')  # Newline


# Prints out a device instance in the terminal by parsing dict
def pretty_print_device(device):
    logging.info('Device Instance Id: %s' % device['id'])
    if 'nickname' in device:
        logging.info('    Nickname: %s' % device['nickname'])
    if 'modelId' in device:
        logging.info('    Model: %s' % device['modelId'])
    logging.info('')  # Newline


@click.group()
@click.option('--project',
              help='Enter the Google Developer Project ID that you want to '
              'use with the registration tool. If you don\'t use this flag, '
              'the tool will use the project listed in the '
              '<client_secret_client-id.json> file you specify with the '
              '--client-secret flag.')
@click.option('--client-secret',
              help='Enter the path and filename for the '
              '<client_secret_client-id.json> file you downloaded from your '
              'developer project. This file is used to infer the Google '
              'Developer Project ID if it was not provided with the --project '
              'flag. If the --project flag and this flag are not used, the '
              'tool will look for this file in the current directory (by '
              'searching for a file named after the client_id stored in the '
              'credentials file).')
@click.option('--verbose', flag_value=True,
              help='Shows detailed JSON response')
@click.option('--api-endpoint', default='embeddedassistant.googleapis.com',
              show_default=True,
              help='Hostname for the Google Assistant API. Do not use this '
              'flag unless explicitly instructed.')
@click.option('--credentials', show_default=True,
              default=os.path.join(click.get_app_dir('google-oauthlib-tool'),
                                   'credentials.json'),
              help='File location of the generated credentials file. The '
              'google-oauthlib-tool generates this file after authorizing '
              'the user with the <client_secret_client-id.json> file. This '
              'credentials file authorizes access to the Google Assistant '
              'API. You can use this flag if the credentials were generated '
              'in a location that is different than the default.')
@click.pass_context
def cli(ctx, project, client_secret, verbose, api_endpoint, credentials):
    try:
        with open(credentials, 'r') as f:
            c = google.oauth2.credentials.Credentials(token=None,
                                                      **json.load(f))
            http_request = google.auth.transport.requests.Request()
            c.refresh(http_request)
    except Exception as e:
        raise click.ClickException('Error loading credentials: %s.\n'
                                   'Run google-oauthlib-tool to initialize '
                                   'new OAuth 2.0 credentials.' % e)
    if project is None:
        if client_secret is None:
            client_secret = 'client_secret_%s.json' % c.client_id
        try:
            with open(client_secret, 'r') as f:
                secret = json.load(f)
                project = secret['installed']['project_id']
        except Exception as e:
            raise click.ClickException('Error loading client secret: %s.\n'
                                       'Run the register tool '
                                       'with --client-secret '
                                       'or --project option.\n'
                                       'Or copy the %s file '
                                       'in the current directory.'
                                       % (e, client_secret))
    ctx.obj['SESSION'] = google.auth.transport.requests.AuthorizedSession(c)
    ctx.obj['API_URL'] = ('https://%s/v1alpha2/projects/%s'
                          % (api_endpoint, project))
    ctx.obj['PROJECT_ID'] = project
    logging.basicConfig(format='',
                        level=logging.DEBUG if verbose else logging.INFO)


@cli.command()
@click.option('--model', required=True,
              help='Enter a globally-unique identifier for this device model; '
              'you should use your project ID as a prefix to help avoid '
              'collisions over the range of all projects (for example, '
              '"my-dev-project-my-led1").')
@click.option('--type', type=click.Choice(['LIGHT', 'SWITCH', 'OUTLET']),
              required=True,
              help='Select the type of device hardware that best aligns with '
              'your device. Select LIGHT if none of the listed choices aligns '
              'with your device.')
@click.option('--trait', multiple=True,
              help='Add traits (abilities) that the device supports. Pass '
              'this flag multiple times to create a list of traits. Refer to '
              'https://developers.google.com/assistant/sdk for a list of '
              'supported traits.')
@click.option('--manufacturer', required=True,
              help='Enter the manufacturer\'s name in this field (for '
              'example, "Assistant SDK developer"). This information may be '
              'shown in the Assistant settings and internal analytics.')
@click.option('--product-name', required=True,
              help='Enter the product name in this field (for example, '
              '"Assistant SDK light").')
@click.option('--description',
              help='Enter a description of the product in this field (for '
              'example, "Assistant SDK light device").')
@click.option('--device', required=True,
              help='Enter an identifier for the device instance. This ID must '
              'be unique within all of the devices registered under the same '
              'Google Developer project.')
@click.option('--nickname',
              help='Enter a nickname for the device. You can use this name '
              'when talking to your Assistant to refer to this device.')
@click.pass_context
def register(ctx, model, type, trait, manufacturer, product_name, description,
             device, nickname):
    """Registers a device model and instance.

    Device model and instance fields can only contain letters, numbers, and the
    following symbols: period (.), hyphen (-), underscore (_), space ( ) and
    plus (+). The first character of a field must be a letter or number.
    """
    ctx.invoke(register_model,
               model=model, type=type, trait=trait,
               manufacturer=manufacturer,
               product_name=product_name,
               description=description)
    ctx.invoke(register_device, device=device, model=model, nickname=nickname)


@cli.command('register-model')
@click.option('--model', required=True,
              help='Enter a globally-unique identifier for this device model; '
              'you should use your project ID as a prefix to help avoid '
              'collisions over the range of all projects (for example, '
              '"my-dev-project-my-led1").')
@click.option('--type', type=click.Choice(['LIGHT', 'SWITCH', 'OUTLET']),
              required=True,
              help='Select the type of device hardware that best aligns with '
              'your device. Select LIGHT if none of the listed choices aligns '
              'with your device.')
@click.option('--trait', multiple=True,
              help='Add traits (abilities) that the device supports. Pass '
              'this flag multiple times to create a list of traits. Refer to '
              'https://developers.google.com/assistant/sdk for a list of '
              'supported traits.')
@click.option('--manufacturer', required=True,
              help='Enter the manufacturer\'s name in this field (for '
              'example, "Assistant SDK developer"). This information may be '
              'shown in the Assistant settings and internal analytics.')
@click.option('--product-name', required=True,
              help='Enter the product name in this field (for example, '
              '"Assistant SDK light").')
@click.option('--description',
              help='Enter a description of the product in this field (for '
              'example, "Assistant SDK light device").')
@click.pass_context
def register_model(ctx, model, type, trait,
                   manufacturer, product_name, description):
    """Registers a device model.

    Device model and instance fields can only contain letters, numbers, and the
    following symbols: period (.), hyphen (-), underscore (_), space ( ) and
    plus (+). The first character of a field must be a letter or number.
    """
    session = ctx.obj['SESSION']

    model_base_url = '/'.join([ctx.obj['API_URL'], 'deviceModels'])
    model_url = '/'.join([model_base_url, model])
    payload = {
        'device_model_id': model,
        'project_id': ctx.obj['PROJECT_ID'],
        'device_type': 'action.devices.types.' + type,
    }
    if trait:
        payload['traits'] = trait
    if manufacturer:
        payload.setdefault('manifest', {})['manufacturer'] = manufacturer
    if product_name:
        payload.setdefault('manifest', {})['productName'] = product_name
    if description:
        payload.setdefault('manifest', {})['deviceDescription'] = description
    logging.debug(json.dumps(payload))
    r = session.get(model_url)
    logging.debug(r.text)
    if r.status_code == 200:
        click.echo('Updating existing device model: %s' % model)
        r = session.put(model_url, data=json.dumps(payload))
    elif r.status_code in (400, 404):
        click.echo('Creating new device model')
        r = session.post(model_base_url, data=json.dumps(payload))
    else:
        raise failed_request_exception('Unknown error occurred', r)
    if r.status_code != 200:
        raise failed_request_exception('Failed to register model', r)
    click.echo('Model %s successfully registered' % model)


@cli.command('register-device')
@click.option('--device', required=True,
              help='Enter an identifier for the device instance. This ID must '
              'be unique within all of the devices registered under the same '
              'Google Developer project.')
@click.option('--model', required=True,
              help='Enter the identifier for an existing device model. This '
              'new device instance will be associated with this device model.')
@click.option('--nickname',
              help='Enter a nickname for the device. You can use this name '
              'when talking to your Assistant to refer to this device.')
@click.pass_context
def register_device(ctx, device, model, nickname):
    """Registers a device instance under an existing device model.

    Device model and instance fields can only contain letters, numbers, and the
    following symbols: period (.), hyphen (-), underscore (_), space ( ) and
    plus (+). The first character of a field must be a letter or number.
    """
    session = ctx.obj['SESSION']

    device_base_url = '/'.join([ctx.obj['API_URL'], 'devices'])
    device_url = '/'.join([device_base_url, device])
    payload = {
        'id': device,
        'model_id': model,
    }
    if nickname:
        payload['nickname'] = nickname

    logging.debug(json.dumps(payload))
    r = session.get(device_url)
    if r.status_code == 200:
        click.echo('Updating existing device: %s' % device)
        session.delete(device_url)
        r = session.post(device_base_url, data=json.dumps(payload))
    elif r.status_code in (400, 404):
        click.echo('Creating new device')
        r = session.post(device_base_url, data=json.dumps(payload))
    else:
        raise failed_request_exception('Failed to check existing device', r)
    if r.status_code != 200:
        raise failed_request_exception('Failed to register device', r)
    click.echo('Device instance %s successfully registered' % device)
    logging.debug(r.text)


@cli.command()
@click.option('--model', 'resource', flag_value='deviceModels', required=True,
              help='Enter the identifier for an existing device model.')
@click.option('--device', 'resource', flag_value='devices', required=True,
              help='Enter the identifier for an existing device instance.')
@click.argument('id')
@click.pass_context
def get(ctx, resource, id):
    """Gets all of the information (fields) for a given device model or
    instance.
    """
    session = ctx.obj['SESSION']

    url = '/'.join([ctx.obj['API_URL'], resource, id])
    r = session.get(url)
    if r.status_code != 200:
        raise failed_request_exception('Failed to get resource', r)

    response = json.loads(r.text)
    if resource == 'deviceModels':
        pretty_print_model(response)
    elif resource == 'devices':
        pretty_print_device(response)
    logging.debug(r.text)


@cli.command()
@click.option('--model', 'resource', flag_value='deviceModels', required=True)
@click.option('--device', 'resource', flag_value='devices', required=True)
@click.pass_context
def list(ctx, resource):
    """Lists all of the device models and/or instances associated with the
    current Google Developer project. To change the current project, use the
    devicetool's --project flag.
    """
    session = ctx.obj['SESSION']

    url = '/'.join([ctx.obj['API_URL'], resource])
    r = session.get(url)
    if r.status_code != 200:
        raise failed_request_exception('Failed to list resources', r)

    response = json.loads(r.text)
    logging.debug(r.text)
    if resource == 'deviceModels':
        for devicemodel in response['deviceModels']:
            pretty_print_model(devicemodel)
    elif resource == 'devices':
        for device in response['devices']:
            pretty_print_device(device)


def main():
    cli(obj={})


if __name__ == '__main__':
    main()
