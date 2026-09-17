from types import SimpleNamespace

from app.visual import GeminiVisualDescriber


def test_gemini_visual_describer_parses_confidence_and_review_decision(tmp_path):
    source = tmp_path / 'inspection.png'
    source.write_bytes(b'png-bytes')

    class FakeModels:
        def generate_content(self, **kwargs):
            assert kwargs['model'] == 'gemini-test'
            assert kwargs['contents'][1].inline_data.mime_type == 'image/png'
            json_text = '{' + chr(34) + 'description' + chr(34) + ':' + chr(34) + 'A red quarantine tray is visible.' + chr(34) + ',' + chr(34) + 'confidence' + chr(34) + ':0.92,' + chr(34) + 'review_required' + chr(34) + ':false}'
            return SimpleNamespace(text=json_text)

    describer = GeminiVisualDescriber(
        model='gemini-test',
        api_key='test-key',
        client=SimpleNamespace(models=FakeModels()),
    )

    result = describer.describe(source, region_ref='#/pictures/1')

    assert result.description == 'A red quarantine tray is visible.'
    assert result.confidence == 0.92
    assert result.review_required is False


def test_gemini_visual_describer_requires_review_for_invalid_model_output(tmp_path):
    source = tmp_path / 'inspection.jpg'
    source.write_bytes(b'jpg-bytes')
    describer = GeminiVisualDescriber(
        model='gemini-test',
        api_key='test-key',
        client=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_: SimpleNamespace(text='not-json')
            )
        ),
    )

    result = describer.describe(source, region_ref='#/pictures/1')

    assert result.description == ''
    assert result.confidence == 0.0
    assert result.review_required is True
    assert 'JSON' in result.reason


def test_gemini_visual_describer_accepts_a_cropped_region():
    class FakeModels:
        def generate_content(self, **kwargs):
            assert kwargs['contents'][1].inline_data.mime_type == 'image/png'
            assert kwargs['contents'][1].inline_data.data == b'cropped-region'
            return SimpleNamespace(text='{"description":"Gauge reads zero.","confidence":0.95,"review_required":false}')

    describer = GeminiVisualDescriber(
        model='gemini-test',
        api_key='test-key',
        client=SimpleNamespace(models=FakeModels()),
    )

    result = describer.describe_region(
        b'cropped-region',
        mime_type='image/png',
        region_ref='#/pictures/1',
        page=2,
    )

    assert result.description == 'Gauge reads zero.'
