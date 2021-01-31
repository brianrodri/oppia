// Copyright 2020 The Oppia Authors. All Rights Reserved.
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
 * @fileoverview Service for managing the authorizations of logged-in users.
 */

import { Injectable, Provider } from '@angular/core';
import { AngularFireModule } from '@angular/fire';
import { AngularFireAuth, AngularFireAuthModule, USE_EMULATOR } from '@angular/fire/auth';
import { downgradeInjectable } from '@angular/upgrade/static';
import { Observable } from 'rxjs';

import { AppConstants } from 'app.constants';
import { ModuleWithProviders, Type } from '@angular/compiler/src/core';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  constructor(private angularFireAuth: AngularFireAuth) {}

  get idToken$(): Observable<string | null> {
    return this.angularFireAuth.idToken;
  }

  async signOutAsync(): Promise<void> {
    return this.angularFireAuth.signOut();
  }

  static get firebaseAuthIsEnabled(): boolean {
    return AppConstants.FIREBASE_AUTH_ENABLED;
  }

  static getModules(): (Type | ModuleWithProviders)[] {
    const modules = [];

    if (AuthService.firebaseAuthIsEnabled) {
      modules.push(AngularFireModule.initializeApp({
        apiKey: AppConstants.FIREBASE_CONFIG_API_KEY,
        authDomain: AppConstants.FIREBASE_CONFIG_AUTH_DOMAIN,
        projectId: AppConstants.FIREBASE_CONFIG_PROJECT_ID,
        storageBucket: AppConstants.FIREBASE_CONFIG_STORAGE_BUCKET,
        messagingSenderId: AppConstants.FIREBASE_CONFIG_MESSAGING_SENDER_ID,
        appId: AppConstants.FIREBASE_CONFIG_APP_ID,
      }));
      modules.push(AngularFireAuthModule);
    }

    return modules;
  }

  static getProviders(): Provider[] {
    const providers = [];

    // TODO(#11462): Move these into shared-component.module.ts after launching
    // Firebase authentication.
    if (AuthService.firebaseAuthIsEnabled) {
      providers.push(AngularFireAuth);
      if (AppConstants.FIREBASE_EMULATOR_ENABLED) {
        providers.push({provide: USE_EMULATOR, useValue: ['localhost', 9099]});
      }
    }

    return providers;
  }
}

angular.module('oppia').factory(
  'AuthService', downgradeInjectable(AuthService));
