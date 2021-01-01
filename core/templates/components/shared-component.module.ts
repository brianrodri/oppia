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
 * @fileoverview Module for the shared components.
 */
import 'core-js/es7/reflect';
import 'zone.js';

import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { BackgroundBannerComponent } from
  './common-layout-directives/common-elements/background-banner.component';
import { AttributionGuideComponent } from
  './common-layout-directives/common-elements/attribution-guide.component';
import { LazyLoadingComponent } from
  './common-layout-directives/common-elements/lazy-loading.component';
import { LoadingDotsComponent } from
  './common-layout-directives/common-elements/loading-dots.component';
import { MaterialModule } from './material.module';
import { TranslatePipe } from 'filters/translate.pipe';
import { SkillMasteryViewerComponent } from
  './skill-mastery/skill-mastery.component';
import { ExplorationEmbedButtonModalComponent } from
  './button-directives/exploration-embed-button-modal.component';
import { KeyboardShortcutHelpModalComponent } from
  'components/keyboard-shortcut-help/keyboard-shortcut-help-modal.component';
import { SharingLinksComponent } from
  './common-layout-directives/common-elements/sharing-links.component';
import { StorySummaryTileDirective } from
  './summary-tile/story-summary-tile.directive';
import { SubtopicSummaryTileDirective } from
  './summary-tile/subtopic-summary-tile.directive';
import { SocialButtonsComponent } from
  'components/button-directives/social-buttons.component';
import { NgbModalModule } from '@ng-bootstrap/ng-bootstrap';
import { ExplorationSummaryTileDirective } from
  './summary-tile/exploration-summary-tile.directive';
import { ProfileLinkImageComponent } from
  'components/profile-link-directives/profile-link-image.component';
import { ProfileLinkTextComponent } from
  'components/profile-link-directives/profile-link-text.component';
import { TakeBreakModalComponent } from
  'pages/exploration-player-page/templates/take-break-modal.component';
import { AngularFireModule } from '@angular/fire';
import { AngularFireAuth, AngularFireAuthModule, USE_EMULATOR } from '@angular/fire/auth';
import { AppConstants } from 'app.constants';
import { BrowserModule } from '@angular/platform-browser';


@NgModule({
  imports: [
    CommonModule,
    MaterialModule,
    NgbModalModule,
    BrowserModule,
    FormsModule,
    AngularFireModule.initializeApp({
      apiKey: AppConstants.FIREBASE_CONFIG_API_KEY,
      authDomain: AppConstants.FIREBASE_CONFIG_AUTH_DOMAIN,
      databaseURL: AppConstants.FIREBASE_CONFIG_DATABASE_URL,
      projectId: AppConstants.FIREBASE_CONFIG_PROJECT_ID,
      storageBucket: AppConstants.FIREBASE_CONFIG_STORAGE_BUCKET,
      messagingSenderId: AppConstants.FIREBASE_CONFIG_MESSAGING_SENDER_ID,
      appId: AppConstants.FIREBASE_CONFIG_APP_ID,
    }),
    AngularFireAuthModule
  ],

  providers: [
    AngularFireAuth,
    {
      provide: USE_EMULATOR,
      useValue: (
        AppConstants.FIREBASE_EMULATOR_ENABLED ? ['localhost', 9099] :
        undefined)
    },
  ],

  declarations: [
    AttributionGuideComponent,
    BackgroundBannerComponent,
    ExplorationEmbedButtonModalComponent,
    ExplorationSummaryTileDirective,
    KeyboardShortcutHelpModalComponent,
    LazyLoadingComponent,
    LoadingDotsComponent,
    ProfileLinkImageComponent,
    ProfileLinkTextComponent,
    SharingLinksComponent,
    SkillMasteryViewerComponent,
    StorySummaryTileDirective,
    SocialButtonsComponent,
    SubtopicSummaryTileDirective,
    TranslatePipe,
    TakeBreakModalComponent
  ],

  entryComponents: [
    BackgroundBannerComponent,
    SharingLinksComponent,
    SkillMasteryViewerComponent, AttributionGuideComponent,
    LazyLoadingComponent, LoadingDotsComponent, SocialButtonsComponent,
    ProfileLinkImageComponent, ProfileLinkTextComponent,
    // These elements will remain here even after migration.
    TakeBreakModalComponent,
    ExplorationEmbedButtonModalComponent,
    KeyboardShortcutHelpModalComponent,
    SkillMasteryViewerComponent,
    SocialButtonsComponent
  ],

  exports: [
    // Modules.
    AngularFireAuthModule,
    FormsModule,
    MaterialModule,
    // Components, directives, and pipes.
    BackgroundBannerComponent,
    ExplorationSummaryTileDirective,
    SharingLinksComponent,
    StorySummaryTileDirective,
    SubtopicSummaryTileDirective,
    TakeBreakModalComponent,
    TranslatePipe
  ],
})

export class SharedComponentsModule { }
