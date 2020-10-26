import json
import urllib
import requests

from odoo import fields, models, api, _

GOOGLE_OAUTH_ENDPOINT = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_PROMPT_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_DRIVE_UPLOAD_API = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart'
GOOGLE_DRIVE_UPDATE_API = 'https://www.googleapis.com/drive/v3/files/'


class GoogleDrive(models.Model):
    _name = 'odoo_addon_auto_backup.google_drive'

    @api.model
    def get_user_redirect_url(self):
        Config = self.env['ir.config_parameter'].sudo()
        base_url = Config.get_param('web.base.url')
        client_id = Config.get_param('abackup_gdrive_client_id')

        params = {
            'client_id': client_id,
            'redirect_uri': base_url + '/screwproof/authentication',
            'access_type': 'offline',
            'response_type': 'code',
            'scope': 'https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/drive.file',
        }

        params_text = '&'.join(['%s=%s' % (key,
                                           urllib.parse.quote(value, safe=''))
                                for (key, value) in params.items()])
        return GOOGLE_USER_PROMPT_URL + '?' + params_text


    @api.model
    def get_access_token(self):
        Config = self.env['ir.config_parameter'].sudo()

        base_url = Config.get_param('web.base.url')
        auth_code = Config.get_param('abackup_gdrive_auth_code')
        refresh_token = Config.get_param('abackup_gdrive_refresh_code', False)
        client_id = Config.get_param('abackup_gdrive_client_id')
        client_secret = Config.get_param('abackup_gdrive_client_secret')

        if auth_code:
            if refresh_token:
                # Request refresh token
                body = {
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'refresh_token': refresh_token,
                    'grant_type': 'refresh_token',
                }
            else:
                # Request new token
                body = {
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'code': auth_code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': base_url + '/screwproof/authentication',
                }

            headers = {"Content-type": "application/x-www-form-urlencoded"}

            req = requests.post(GOOGLE_OAUTH_ENDPOINT, data=body, headers=headers)
            req.raise_for_status()

            req_json = req.json()
            if req_json.get('refresh_token') is not None:
                self.env['ir.config_parameter'].sudo().set_param('abackup_gdrive_refresh_code', req_json.get('refresh_token'))

            return req_json.get('access_token')

        return False

    def upload(self, binary_stream, file_name):
        token = self.get_access_token()
        if token:
            # Upload file
            para = json.dumps({
                'name': file_name,
                'originalFilename': file_name
            })
            headers = {"Authorization": "Bearer %s" % token}
            files = {
                'data': ('metadata', json.dumps(para), 'application/json; charset=UTF-8'),
                'file': ('mimeType', binary_stream)
            }

            req = requests.post(GOOGLE_DRIVE_UPLOAD_API, headers=headers, files=files)
            req.raise_for_status()

            # Update file name
            file_id = req.json().get('id')
            body = {
                'name': file_name,
            }
            req = requests.patch(GOOGLE_DRIVE_UPDATE_API + file_id, headers=headers, json=body)
            req.raise_for_status()
