#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from horizon.test import firefox_binary
from openstack_dashboard.test.integration_tests import helpers

from os import listdir
from os.path import join
from os import remove


class TestDownloadRCFile(helpers.AdminTestCase):

    _directory = firefox_binary.WebDriver.TEMPDIR
    _openrc_template = "-openrc.sh"

    def setUp(self):
        super(TestDownloadRCFile, self).setUp()
        username = self.TEST_USER_NAME
        tenant_name = self.HOME_PROJECT
        projects_page = self.home_pg.go_to_identity_projectspage()
        tenant_id = projects_page.get_project_id_from_row(tenant_name)
        self.actual_dict = {'OS_USERNAME': username,
                            'OS_TENANT_NAME': tenant_name,
                            'OS_TENANT_ID': tenant_id}

        def cleanup():
            remove(join(self._directory, listdir(self._directory)[0]))

        self.addCleanup(cleanup)

    def test_download_rc_v2_file(self):
        """This is a basic scenario test:
        Steps:
        1) Login to Horizon Dashboard as admin user
        2) Navigate to Project > Compute > Access & Security > API Access tab
        3) Click on "Download OpenStack RC File v2.0" button
        4) File named by template "<tenant_name>-openrc.sh" must be downloaded
        5) Check that username, tenant name and tenant id correspond to current
        username, tenant name and tenant id
        """
        api_access_page = self.home_pg.\
            go_to_compute_accessandsecurity_apiaccesspage()
        api_access_page.download_openstack_rc_file(
            2, self._directory, self._openrc_template)
        cred_dict = api_access_page.get_credentials_from_file(
            2, self._directory, self._openrc_template)
        self.assertEqual(cred_dict, self.actual_dict)

    def test_download_rc_v3_file(self):
        """This is a basic scenario test:
        Steps:
        1) Login to Horizon Dashboard as admin user
        2) Navigate to Project > Compute > Access & Security > API Access tab
        3) Click on "Download OpenStack RC File v3" button
        4) File named by template "<tenant_name>-openrc.sh" must be downloaded
        5) Check that username, project name and project id correspond to
        current username, tenant name and tenant id
        """
        api_access_page = self.home_pg.\
            go_to_compute_accessandsecurity_apiaccesspage()
        api_access_page.download_openstack_rc_file(
            3, self._directory, self._openrc_template)
        cred_dict = api_access_page.get_credentials_from_file(
            3, self._directory, self._openrc_template)
        self.assertEqual(cred_dict, self.actual_dict)


class TestViewCredentials(helpers.AdminTestCase):

    def test_view_credentials(self):
        """This test checks user credentials
        Steps:
        1) Login to Horizon Dashboard as admin user
        2) Navigate to Project > Compute > Access & Security > API Access tab
        3) Click on "View Credentials" button
        4) View opened dialog window "User Credentials", check its contents.
        Following fields in "User Credentials" dialog must be displayed:
        User Name; Project Name; Project ID; Authentication URL.
        """
        api_access_page = self.home_pg.\
            go_to_compute_accessandsecurity_apiaccesspage()
        view_credentials_dict = api_access_page.view_user_credentials()

        user_name = self.TEST_USER_NAME
        project_name = self.HOME_PROJECT
        auth_url = api_access_page.get_service_endpoint_from_row('Identity')
        projects_page = self.home_pg.go_to_identity_projectspage()
        project_id = projects_page.get_project_id_from_row(project_name)
        actual_dict = {'User Name': user_name, 'Project Name': project_name,
                       'Project ID': project_id,
                       'Authentication URL': auth_url}
        self.assertEqual(actual_dict, view_credentials_dict)
