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

require('domain/utilities/url-interpolation.service.ts');

angular.module('oppia').directive('improvementsTab', [
  'UrlInterpolationService', function(UrlInterpolationService) {
    return {
      restrict: 'E',
      scope: {},
      templateUrl: UrlInterpolationService.getDirectiveTemplateUrl(
        '/pages/exploration-editor-page/improvements-tab/' +
        'improvements-tab.directive.html'),
      controller: ['$scope', $scope => {
        const COMPLETION_BAR_ARC_RADIUS = 58;
        const COMPLETION_BAR_ARC_LENGTH = Math.PI * COMPLETION_BAR_ARC_RADIUS;
        var completionRate = 0.6;
        var explorationHealth = 'critical';
        var improvementsPending = 0;

        $scope.getStaticImageUrl = function(imagePath) {
          return UrlInterpolationService.getStaticImageUrl(imagePath);
        };

        $scope.getImprovementsPending = function() {
          return improvementsPending;
        };

        $scope.cycleExplorationHealth = function() {
          if (explorationHealth === 'critical') {
            explorationHealth = 'healthy';
          } else if (explorationHealth === 'healthy') {
            explorationHealth = 'warning';
          } else if (explorationHealth === 'warning') {
            explorationHealth = 'critical';
          }
        };

        $scope.getExplorationHealth = function() {
          return explorationHealth;
        };

        $scope.refreshCompletionRate = function() {
          completionRate = Math.random();
        };

        $scope.getCompletionRateAsPercent = function() {
          return Math.round(100 * completionRate) + '%';
        };

        $scope.getCompletionBarStyle = function() {
          return {
            'stroke-dasharray': COMPLETION_BAR_ARC_LENGTH,
            'stroke-dashoffset': (
              COMPLETION_BAR_ARC_LENGTH * (1 - completionRate)),
          };
        };
      }],
    };
  }
]);
