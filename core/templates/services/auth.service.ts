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

import { Injectable, Optional } from '@angular/core';
import { AngularFireModule } from '@angular/fire';
import { AngularFireAuth, AngularFireAuthModule, USE_EMULATOR } from '@angular/fire/auth';
import { downgradeInjectable } from '@angular/upgrade/static';
import { Observable, of } from 'rxjs';

import { AppConstants } from 'app.constants';
import { ModuleWithProviders } from '@angular/compiler/src/core';


@Injectable({
  providedIn: 'root'
})
export class AuthService {
  constructor(@Optional() private angularFireAuth: AngularFireAuth) {}

  get idToken$(): Observable<string | null> {
    return this.angularFireAuth?.idToken ?? of(null);
  }

  async signOutAsync(): Promise<void> {
    await this.angularFireAuth?.signOut();
  }

  static get firebaseAuthIsEnabled(): boolean {
    return AppConstants.FIREBASE_AUTH_ENABLED;
  }

  static forRoot(): ModuleWithProviders[] {
    if (AuthService.firebaseAuthIsEnabled) {
      return [
        AngularFireModule.initializeApp(
          {
            apiKey: AppConstants.FIREBASE_CONFIG_API_KEY,
            authDomain: AppConstants.FIREBASE_CONFIG_AUTH_DOMAIN,
            projectId: AppConstants.FIREBASE_CONFIG_PROJECT_ID,
            storageBucket: AppConstants.FIREBASE_CONFIG_STORAGE_BUCKET,
            messagingSenderId: AppConstants.FIREBASE_CONFIG_MESSAGING_SENDER_ID,
            appId: AppConstants.FIREBASE_CONFIG_APP_ID,
          }),
        {
          ngModule: AngularFireAuthModule,
          providers: [
            AngularFireAuth,
            {
              provide: USE_EMULATOR,
              useValue: AppConstants.FIREBASE_EMULATOR_ENABLED ?
                ['localhost', 9099] : undefined,
            },
          ]
        }
      ];
    }
    return [];
  }
}

angular.module('oppia').factory(
  'AuthService', downgradeInjectable(AuthService));
