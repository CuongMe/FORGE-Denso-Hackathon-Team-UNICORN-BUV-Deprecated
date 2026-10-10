'use client';

import Image from 'next/image';
import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';

import { getDocumentVisualDetections } from '@/lib/api';
import type { VisualDetections } from '@/lib/types';

export function FlorenceImageViewer({ documentId, src, alt }: { documentId: string; src: string; alt: string }) {
  const t = useTranslations();
  const [state, setState] = useState<{ documentId: string; result?: VisualDetections; unavailable?: boolean }>();

  useEffect(() => {
    let active = true;
    void getDocumentVisualDetections(documentId)
      .then((result) => { if (active) setState({ documentId, result }); })
      .catch(() => { if (active) setState({ documentId, unavailable: true }); });
    return () => { active = false; };
  }, [documentId]);
  const current = state?.documentId === documentId ? state : undefined;
  const result = current?.result;
  const unavailable = current?.unavailable === true;

  return <div className="forge-florence-image-viewer">
    <div className="forge-florence-image-stage">
      <Image src={src} alt={alt} fill sizes="(max-width: 900px) 90vw, 850px" unoptimized />
      {result && <svg className="forge-florence-boxes" viewBox={`0 0 ${result.image_width} ${result.image_height}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label={t('documents.florenceOverlay')}>
        <title>{t('documents.florenceOverlay')}</title>
        {result.detections.map(({ label, bbox }, index) => {
          const [x1, y1, x2, y2] = bbox;
          return <g key={`${index}-${label}`}>
            <rect className="forge-florence-box" x={x1} y={y1} width={x2 - x1} height={y2 - y1} vectorEffect="non-scaling-stroke" />
            <text className="forge-florence-label" x={x1 + 3} y={y1 > 24 ? y1 - 5 : y1 + 20}>{label}</text>
          </g>;
        })}
      </svg>}
    </div>
    <div className="forge-florence-image-status" aria-live="polite">
      <strong>Florence-2</strong>
      {result && <span>{t('documents.florenceDetectionCount', { count: result.detections.length })}</span>}
      {!result && !unavailable && <span>{t('documents.florenceLoading')}</span>}
      {unavailable && <span>{t('documents.florenceUnavailable')}</span>}
    </div>
  </div>;
}
