// @flow
import {createSelector} from 'reselect'

import {selectors as pipetteSelectors} from '../pipettes'
import {selectors as labwareIngredSelectors} from '../labware-ingred/reducers'
import {selectors as steplistSelectors} from '../steplist'
import {selectors as fileDataSelectors} from '../file-data'
import {allWellContentsForSteps} from './well-contents'

import {
  generateSubsteps,
  type GetIngreds
} from '../steplist/generateSubsteps' // TODO Ian 2018-04-11 move generateSubsteps closer to this substeps.js file?

import type {Selector} from '../types'
import type {StepIdType} from '../form-types'
import type {SubstepItemData} from '../steplist/types'
import type {WellContentsByLabware} from './well-contents'

const getIngredsFactory = (
  wellContentsByLabware: WellContentsByLabware,
  ingredNames: {[ingredId: string]: string}
): GetIngreds => (labware, well) => {
  const wellContents = (wellContentsByLabware &&
    wellContentsByLabware[labware] &&
    wellContentsByLabware[labware][well])

  return wellContents.groupIds.map(id => ({
    id: id,
    name: ingredNames[id]
  })) || []
}

type AllSubsteps = {[StepIdType]: ?SubstepItemData}
export const allSubsteps: Selector<AllSubsteps> = createSelector(
  steplistSelectors.validatedForms,
  pipetteSelectors.equippedPipettes,
  labwareIngredSelectors.getLabwareTypes,
  labwareIngredSelectors.getIngredientNames,
  allWellContentsForSteps,
  steplistSelectors.orderedSteps,
  fileDataSelectors.robotStateTimeline,
  fileDataSelectors.getInitialRobotState,
  (
    validatedForms,
    allPipetteData,
    allLabwareTypes,
    ingredNames,
    _allWellContentsForSteps,
    orderedSteps,
    robotStateTimeline,
    initialRobotState
  ) => {
    return orderedSteps
    .reduce((acc: AllSubsteps, stepId, timelineIndex) => {
      // TODO: Ian 2018-08-21 make a util fn or selector for prev timeline frame,
      // using initialRobotState if timelineIndex === 0, otherwise [timelineIndex - 1]
      // and using lastValidRobotState when timelineIndex exceeds timeline len.
      // That fn/selector would also be useful in tip-contents and well-contents.
      const prevRobotState = robotStateTimeline.timeline[timelineIndex - 1]
        ? robotStateTimeline.timeline[timelineIndex - 1].robotState
        : initialRobotState

      const substeps = generateSubsteps(
        validatedForms[stepId],
        allPipetteData,
        (labwareId: string) => allLabwareTypes[labwareId],
        getIngredsFactory(_allWellContentsForSteps[timelineIndex], ingredNames),
        prevRobotState,
        stepId
      )
      return {
        ...acc,
        [stepId]: substeps
      }
    }, {})
  }
)
