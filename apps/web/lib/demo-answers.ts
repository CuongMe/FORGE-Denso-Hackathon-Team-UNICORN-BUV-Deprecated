export const demoAnswers = [
  {
    id: 'loto',
    questionKey: 'ask.demoLotoQuestion',
    answerKey: 'ask.demoLotoAnswer',
    sourcesKey: 'ask.demoLotoSources',
    evidenceChunkIds: ['EHS-ALERT-003:chunk-0001', 'EHS-ALERT-003:chunk-0002'],
    evidenceFacts: ['Only trained and authorized personnel may perform lockout/tagout', 'verify pneumatic pressure = 0 MPa'],
  },
  {
    id: 'defects',
    questionKey: 'ask.demoDefectQuestion',
    answerKey: 'ask.demoDefectAnswer',
    sourcesKey: 'ask.demoDefectSources',
    evidenceChunkIds: ['SOP-QLT-014:chunk-0002', 'SOP-QLT-014:chunk-0003'],
    evidenceFacts: ['Notify the team leader within 10 minutes', 'Create an NCR within 30 minutes for a Critical defect or when defect quantity is 3 or more'],
  },
  {
    id: 'maintenance',
    questionKey: 'ask.demoMaintenanceQuestion',
    answerKey: 'ask.demoMaintenanceAnswer',
    sourcesKey: 'ask.demoMaintenanceSources',
    evidenceChunkIds: ['MAINT-CHK-007:chunk-0002', 'MAINT-CHK-007:chunk-0003'],
    evidenceFacts: ['Air pressure, Standard / limit = 0.50-0.60 MPa', 'servo motor temperature reaches 65 °C or higher'],
  },
] as const;
