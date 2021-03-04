// Copyright 2014 The Oppia Authors. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS-IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Utilities for user creation, login and privileging when
 * carrying out end-to-end testing with protractor.
 */

var FirebaseAdmin = require('firebase-admin');
var general = require('./general.js');
var waitFor = require('./waitFor.js');
var action = require('./action.js');
var AdminPage = require('./AdminPage.js');
var adminPage = new AdminPage.AdminPage();

var login = async function(email) {
  // Use of element and action is not possible because sometimes protractor
  // does not begin on an angular page.
  var driver = browser.driver;
  // The full url is also necessary.
  await driver.get(general.SERVER_URL_PREFIX + '/');

  var loginButton = element(by.css('.protractor-test-login-button'));
  await waitFor.elementToBeClickable(loginButton, 'login button not found');
  await loginButton.click();

  await waitFor.alertToBePresent();
  const alert = await browser.switchTo().alert();
  await alert.sendKeys(email);
  await alert.accept();

  await waitFor.pageToFullyLoad();
};

var logout = async function() {
  // Use of action is not possible because logout page is non-angular.
  var driver = browser.driver;
  await driver.get(general.SERVER_URL_PREFIX);
  await waitFor.pageToFullyLoad();
  await general.openProfileDropdown();
  var logoutLink = element(by.css('.protractor-test-logout-link'));
  await action.click('logout link from dropdown', logoutLink);
  await waitFor.pageToFullyLoad();
};

// The user needs to log in immediately before this method is called. Note
// that this will fail if the user already has a username.
var _completeSignup = async function(username) {
  await waitFor.pageToFullyLoad();
  var usernameInput = element(by.css('.protractor-test-username-input'));
  var agreeToTermsCheckbox = element(
    by.css('.protractor-test-agree-to-terms-checkbox'));
  var registerUser = element(by.css('.protractor-test-register-user'));
  await action.sendKeys('Username input', usernameInput, username);
  await action.click('agreeToTerms Checkbox', agreeToTermsCheckbox);
  await action.click('Register User button', registerUser);
  await waitFor.pageToFullyLoad();
};

var _grantSuperAdminPrivileges = async function(email) {
  const user = await FirebaseAdmin.auth().getUserByEmail(email.toLowerCase());
  await FirebaseAdmin.auth().setCustomUserClaims(
    user.uid, {role: 'super_admin'});
  // We need to logout and login once more to refresh the user's privileges.
  await logout();
  await login(email);
};

var completeLoginFlowFromStoryViewerPage = async function(email, username) {
  await login(email);
  await _completeSignup(username);
};

var createUser = async function(email, username) {
  await createAndLoginUser(email, username);
  await logout();
};

var createAndLoginUser = async function(email, username) {
  await login(email);
  await _completeSignup(username);
};

var createModerator = async function(email, username) {
  await login(email);
  await _completeSignup(username);
  await _grantSuperAdminPrivileges(email);
  await adminPage.get();
  await adminPage.updateRole(username, 'moderator');
  await logout();
};

var createAdmin = async function(email, username) {
  await createAndLoginAdminUser(email, username);
  await logout();
};

var createAndLoginAdminUser = async function(email, username) {
  await login(email);
  await _completeSignup(username);
  await _grantSuperAdminPrivileges(email);
  await adminPage.get();
  await adminPage.updateRole(username, 'admin');
};

var createAdminMobile = async function(email, username) {
  await createAndLoginAdminUserMobile(email, username);
  await logout();
};

var createAndLoginAdminUserMobile = async function(email, username) {
  await login(email);
  await _completeSignup(username);
  await _grantSuperAdminPrivileges(email);
};

var isAdmin = async function() {
  return await element(by.css('.protractor-test-admin-text')).isPresent();
};

exports.isAdmin = isAdmin;
exports.login = login;
exports.logout = logout;
exports.completeLoginFlowFromStoryViewerPage = (
  completeLoginFlowFromStoryViewerPage);
exports.createUser = createUser;
exports.createAndLoginUser = createAndLoginUser;
exports.createModerator = createModerator;
exports.createAdmin = createAdmin;
exports.createAndLoginAdminUser = createAndLoginAdminUser;
exports.createAdminMobile = createAdminMobile;
exports.createAndLoginAdminUserMobile = createAndLoginAdminUserMobile;
