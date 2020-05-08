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
 * @fileoverview Constants for the improvements tab.
 */

export class ImprovementsTabConstants {
  public static readonly EXPLORATION_HEALTH_TYPE_HEALTHY = 'healthy';
  public static readonly EXPLORATION_HEALTH_TYPE_WARNING = 'warning';
  public static readonly EXPLORATION_HEALTH_TYPE_CRITICAL = 'critical';
  public static readonly EXPLORATION_HEALTH_TYPES: readonly string[] = [
    ImprovementsTabConstants.EXPLORATION_HEALTH_TYPE_HEALTHY,
    ImprovementsTabConstants.EXPLORATION_HEALTH_TYPE_WARNING,
    ImprovementsTabConstants.EXPLORATION_HEALTH_TYPE_CRITICAL,
  ];

  public static readonly COMPLETION_BAR_ARC_RADIUS = 58;
  public static readonly COMPLETION_BAR_ARC_LENGTH = (
    // We use PI here because the graph's shape is a half-circle.
    Math.PI * ImprovementsTabConstants.COMPLETION_BAR_ARC_RADIUS);
}
