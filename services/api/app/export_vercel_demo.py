from __future__ import annotations

import csv
import json
from pathlib import Path

from app.corpus import PROJECT_ROOT, list_demo_documents, load_source_pack_chunks


OUTPUT_PATH = PROJECT_ROOT / 'apps' / 'web' / 'data' / 'denso-corpus.json'
PACK_PATH = PROJECT_ROOT / 'data' / 'denso_factory_hack_data_prep'
VERIFIED_OCR_TEXT = {
    'IMG-SAFE-001:chunk-0001': 'VI: Giới hạn tốc độ trong xưởng: 8 km/h. 1 EN: Factory speed limit: 8 km/h.',
    'IMG-SAFE-001:chunk-0002': 'VI: Bấm còi tại góc khuất và cửa ra vào. 2 EN: Sound horn at blind corners and doorways.',
    'IMG-SAFE-001:chunk-0003': 'VI: Không đi bộ dưới càng nâng hoặc tải đang nâng. 3 EN: Never walk under raised forks or a raised load.',
    'IMG-SAFE-001:chunk-0004': 'VI: Giữ khoảng cách tối thiểu 3 m với người đi bộ. 4 EN: Keep at least 3 m from pedestrians.',
    'IMG-SAFE-001:chunk-0005': 'VI: Dừng và báo cáo nếu đèn cảnh báo không hoạt động. 5 EN: Stop and report if warning lights do not work.',
}


def export_demo_corpus() -> tuple[int, int]:
    with (PACK_PATH / 'manifest.csv').open(encoding='utf-8-sig', newline='') as stream:
        expected_ids = {row['doc_id'] for row in csv.DictReader(stream)}

    chunks = load_source_pack_chunks()
    for chunk in chunks:
        if verified_text := VERIFIED_OCR_TEXT.get(chunk.chunk_id):
            chunk.content = verified_text
    documents = list_demo_documents(chunks)
    chunk_ids = {chunk.doc_id for chunk in chunks if chunk.content.strip()}
    missing = expected_ids - chunk_ids
    if missing:
        raise RuntimeError(f'Denso source files produced no searchable text: {", ".join(sorted(missing))}.')

    payload = {
        'schema_version': 1,
        'source_pack': 'denso_factory_hack_data_prep',
        'documents': documents,
        'chunks': [chunk.model_dump(mode='json') for chunk in chunks],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix('.tmp')
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n',
        encoding='utf-8',
    )
    temporary.replace(OUTPUT_PATH)
    return len(documents), len(chunks)


def main() -> None:
    documents, chunks = export_demo_corpus()
    print(f'Exported {documents} Denso sources and {chunks} searchable chunks to {OUTPUT_PATH}.')


if __name__ == '__main__':
    main()
