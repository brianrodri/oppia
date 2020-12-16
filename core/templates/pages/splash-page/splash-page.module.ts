// Copyright 2019 The Oppia Authors. All Rights Reserved.
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
 * @fileoverview Module for the splash page.
 */

import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http';
import { APP_INITIALIZER, NgModule, StaticProvider } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { downgradeComponent, downgradeModule } from '@angular/upgrade/static';
import { OppiaAngularRootComponent } from 'components/oppia-angular-root.component';
import { SharedComponentsModule } from 'components/shared-component.module';
import { platformFeatureInitFactory, PlatformFeatureService } from 'services/platform-feature.service';
import { RequestInterceptor } from 'services/request-interceptor.service';

import { AngularFireModule } from '@angular/fire';
import { AngularFireAuthModule, USE_EMULATOR } from '@angular/fire/auth';
import { FirebaseUIModule, firebase, firebaseui } from 'firebaseui-angular';
import { AppConstants } from 'app.constants';

const FIREBASE_UI_AUTH_CONFIG: firebaseui.auth.Config = {
  signInFlow: 'popup',
  signInOptions: [
    {
      provider: firebase.auth.EmailAuthProvider.PROVIDER_ID,
      requireDisplayName: false
    }
  ],
  privacyPolicyUrl: '/privacy-policy',
  signInSuccessUrl: '/signup',
  tosUrl: '/terms',
};

@NgModule({
  imports: [
    BrowserModule,
    FormsModule,
    HttpClientModule,
    SharedComponentsModule,
    AngularFireModule.initializeApp(AppConstants.FIREBASE_ENVIRONMENT.config),
    AngularFireAuthModule,
    FirebaseUIModule.forRoot(FIREBASE_UI_AUTH_CONFIG),
  ],
  declarations: [
    OppiaAngularRootComponent
  ],
  entryComponents: [
    OppiaAngularRootComponent
  ],
  providers: [
    {
      provide: USE_EMULATOR,
      useValue: (
        AppConstants.FIREBASE_ENVIRONMENT.production ? undefined :
        ['localhost', 9099])
    },
    {
      provide: HTTP_INTERCEPTORS,
      useClass: RequestInterceptor,
      multi: true
    },
    {
      provide: APP_INITIALIZER,
      useFactory: platformFeatureInitFactory,
      deps: [PlatformFeatureService],
      multi: true
    }
  ],
  exports: [
    FirebaseUIModule
  ],
})
class SplashPageModule {
  // Empty placeholder method to satisfy the `Compiler`.
  ngDoBootstrap() {}
}

const bootstrapFn = (extraProviders: StaticProvider[]) => {
  const platformRef = platformBrowserDynamic(extraProviders);
  return platformRef.bootstrapModule(SplashPageModule);
};
const downgradedModule = downgradeModule(bootstrapFn);

declare var angular: ng.IAngularStatic;

angular.module('oppia').requires.push(downgradedModule);

angular.module('oppia').directive(
  // This directive is the downgraded version of the Angular component to
  // bootstrap the Angular 8.
  'oppiaAngularRoot',
  downgradeComponent({
    component: OppiaAngularRootComponent
  }) as angular.IDirectiveFactory);
