// Copyright 2018 The Oppia Authors. All Rights Reserved.
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
 * @fileoverview Directive for the exploration improvements tab in the
 * exploration editor.
 */

import { ImprovementsTabConstants } from
  'pages/exploration-editor-page/improvements-tab/improvements-tab.constants';

require('components/improvements-directives/completion-graph.directive.ts');

require('domain/utilities/url-interpolation.service.ts');

angular.module('oppia').directive('improvementsTab', [
  'UrlInterpolationService', function(UrlInterpolationService) {
    return {
      restrict: 'E',
      scope: {},
      templateUrl: UrlInterpolationService.getDirectiveTemplateUrl(
        '/pages/exploration-editor-page/improvements-tab/' +
        'improvements-tab.directive.html'),
      controller: ['$scope', function($scope) {
        var completionRate = 0.6;
        var improvementsPending = 2;
        var explorationHealth = 'critical';

        $scope.getStaticImageUrl = (
          imageUrl => UrlInterpolationService.getStaticImageUrl(imageUrl));

        $scope.reroll = () => {
          completionRate = Math.random();
          improvementsPending = (improvementsPending + 1) % 3;
          explorationHealth = ImprovementsTabConstants.EXPLORATION_HEALTH_TYPES[
            improvementsPending];
        };

        $scope.getCompletionRate = () => completionRate;
        $scope.getCompletionRateAsPercent = (
          () => Math.round(100 * $scope.getCompletionRate()) + '%');
        $scope.getImprovementsPending = () => improvementsPending;
        $scope.getExplorationHealth = () => explorationHealth;
      }],
    };
  }
]);
