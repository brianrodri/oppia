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
 * @fileoverview Unit tests for AuthService.
 */

import { TestBed } from '@angular/core/testing';
import { AngularFireAuth } from '@angular/fire/auth';
import { of } from 'rxjs';
import { marbles } from 'rxjs-marbles';

import { AuthService } from 'services/auth.service';
import { MockAngularFireAuth } from 'tests/unit-test-utils';

describe('Auth service', () => {
  const setUpSystemUnderTest = (
    (idTokenSource$ = of(null)): [AngularFireAuth, AuthService] => {
      const mockAngularFireAuth = new MockAngularFireAuth(idTokenSource$);

      TestBed.configureTestingModule({
        providers: [
          {provide: AngularFireAuth, useValue: mockAngularFireAuth},
          AuthService,
        ]
      });

      return [TestBed.inject(AngularFireAuth), TestBed.inject(AuthService)];
    });

  it('should resolve when sign out succeeds', async() => {
    const [angularFireAuth, authService] = setUpSystemUnderTest();

    spyOn(angularFireAuth, 'signOut').and.resolveTo();

    await expectAsync(authService.signOutAsync()).toBeResolvedTo();
  });

  it('should reject when sign out fails', async() => {
    const [angularFireAuth, authService] = setUpSystemUnderTest();

    spyOn(angularFireAuth, 'signOut').and.rejectWith(new Error('fail'));

    await expectAsync(authService.signOutAsync()).toBeRejectedWithError('fail');
  });

  it('should emit nothing when subscription is too early', marbles(m => {
    // Subscribing to the service's idToken$ emits nothing for early observers
    // because the source hasn't produced anything yet. The subscription ends
    // before 'a' is emitted, so a value is never observed.
    const sourceIdTokens = m.hot('-----a-');
    const expectedObservations = '----   ';
    const givenSubscription = '   -^-!   ';

    const [, authService] = setUpSystemUnderTest(sourceIdTokens);

    m.expect(authService.idToken$, givenSubscription)
      .toBeObservable(expectedObservations, {N: null});
  }));

  it('should emit new values after subscribing', marbles(m => {
    const sourceIdTokens = m.hot('-a---b---');
    // The early observer will only see b.
    const earlyObservations = '   -----b---';
    const earlySubscription = '   ---^-----';
    // The late observer will not see anything.
    const lateObservations = '    ---------';
    const lateSubscription = '    -------^-';

    const [, authService] = setUpSystemUnderTest(sourceIdTokens);

    m.expect(authService.idToken$, earlySubscription)
      .toBeObservable(earlyObservations);
    m.expect(authService.idToken$, lateSubscription)
      .toBeObservable(lateObservations);
  }));

  it('should emit null when the source errors', marbles(m => {
    // Even though the source emits an error (represented with the # character),
    // the subscriber just observes a null value and continues, rather than
    // ending abruptly from the same error.
    const sourceIdTokens = m.hot('a---#');
    const expectedObservations = '----#';
    const givenSubscription = '   --^--';

    const [, authService] = setUpSystemUnderTest(sourceIdTokens);

    m.expect(authService.idToken$, givenSubscription)
      .toBeObservable(expectedObservations);
  }));

  it('should continue to emit null after the source errors', marbles(m => {
    // The subscription will see the error and immediately cancel as a
    // consequence.
    const sourceIdTokens = m.hot('-#    ');
    const expectedObservations = '---#  ';
    const givenSubscription = '   ---^  ';

    const [, authService] = setUpSystemUnderTest(sourceIdTokens);

    m.expect(authService.idToken$, givenSubscription)
      .toBeObservable(expectedObservations);
  }));

  it('should not use firebase by default', () => {
    expect(AuthService.firebaseAuthIsEnabled).toBeFalse();
  });

  it('should return empty modules and providers when auth is disabled', () => {
    spyOnProperty(AuthService, 'firebaseAuthIsEnabled', 'get')
      .and.returnValue(false);

    expect(AuthService.forRoot().length).toEqual(0);
  });

  it('should return empty modules and providers when auth is disabled', () => {
    spyOnProperty(AuthService, 'firebaseAuthIsEnabled', 'get')
      .and.returnValue(true);

    expect(AuthService.forRoot().length).toBeGreaterThan(0);
  });
});
