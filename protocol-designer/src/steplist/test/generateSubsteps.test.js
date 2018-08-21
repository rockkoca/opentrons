// @flow
import {partitionCommandsByTipUse} from '../generateSubsteps'

const fakeCommand = (commandType: string) =>
  ({command: commandType})

// TODO IMMEDIATELY this isn't working right for distribute
describe('partitionCommandsByTipUse', () => {
  const tiprackId = 'someTiprackId'
  const prevTiprackId = 'otherTiprackId'
  const commands0 = [
    'aspirate',
    'dispense',
    'touch-tip',
    'dispense',
    'touch-tip'
  ].map(fakeCommand)

  const commands1 = [
    'aspirate',
    'dispense',
    'blow-out'
  ].map(fakeCommand)

  test('empty case', () => {
    const expected = [{commands: [], primaryTipLocation: null}]
    const result = partitionCommandsByTipUse([])
    expect(result).toEqual(expected)
  })

  test('fresh tip (not "never")', () => {
    const expected = [
      {
        // tips used in this partition. From pick-up-tip.
        // (For 8-channel, there's 8 here.)
        primaryTipLocation: {labware: tiprackId, well: 'A1'},
        // a set of commands using those tips.
        // all the pick-up-tip and drop-tip commands are filtered out
        // (b/c they're not useful, but are confusing)
        commands: commands0
      },
      {
        primaryTipLocation: {labware: tiprackId, well: 'B1'},
        commands: commands1
      }
    ]

    const result = partitionCommandsByTipUse([
      {command: 'pick-up-tip', params: {labware: tiprackId, well: 'A1'}},
      ...commands0,
      {command: 'drop-tip'},
      {command: 'pick-up-tip', params: {labware: tiprackId, well: 'B1'}},
      ...commands1
    ])
    expect(result).toEqual(expected)
  })

  test('used tip (with "never")', () => {
    const initialTip = {labware: prevTiprackId, well: 'A1'}
    const expected = [
      {
        // tips used in this partition. From pick-up-tip.
        // (For 8-channel, there's 8 here.)
        primaryTipLocation: initialTip,
        // a set of commands using those tips.
        // all the pick-up-tip and drop-tip commands are filtered out
        // (b/c they're not useful, but are confusing)
        commands: commands0
      },
      {
        primaryTipLocation: {labware: tiprackId, well: 'B1'},
        commands: commands1
      }
    ]

    const result = partitionCommandsByTipUse([
      // reusing tip, no pick-up-tip here
      ...commands0,
      {command: 'drop-tip'},
      {command: 'pick-up-tip', params: {labware: tiprackId, well: 'B1'}},
      ...commands1
    ], initialTip)
    expect(result).toEqual(expected)
  })
})
