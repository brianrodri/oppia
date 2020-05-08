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
 * @fileoverview Directive for the completion graph used in the improvements
 * tab.
 */

import { ImprovementsTabConstants } from
  'pages/exploration-editor-page/improvements-tab/improvements-tab.constants';

require('domain/utilities/url-interpolation.service.ts');

angular.module('oppia').directive('completionGraph', [
  'UrlInterpolationService', function(UrlInterpolationService) {
    return {
      restrict: 'E',
      scope: { completionRate: '<' },
      templateUrl: UrlInterpolationService.getDirectiveTemplateUrl(
        '/components/statistics-directives/completion-graph.directive.html'),
      controller: ['$scope', function($scope) {
        $scope.getCompletionBarStyle = () => ({
          'stroke-dasharray': (
            ImprovementsTabConstants.COMPLETION_BAR_ARC_LENGTH),
          'stroke-dashoffset': (
            (1 - $scope.completionRate) *
              ImprovementsTabConstants.COMPLETION_BAR_ARC_LENGTH),
        });
      }],
    };
  }
]);
