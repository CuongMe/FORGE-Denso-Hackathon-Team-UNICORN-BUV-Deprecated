import { describe, expect, it } from 'vitest';

import { getDemoUploadStages } from '@/lib/demo-upload';

describe('demo upload stages', () => {
  it('shows visual analysis for images and table extraction for documents', () => {
    expect(getDemoUploadStages({ name: 'safety.webp', type: 'image/webp' })).toContain('vlm_analysis');
    expect(getDemoUploadStages({ name: 'maintenance.xlsx', type: '' })).toContain('table_extraction');
    expect(getDemoUploadStages({ name: 'maintenance.xls', type: 'application/vnd.ms-excel' })).toContain('table_extraction');
  });
});
