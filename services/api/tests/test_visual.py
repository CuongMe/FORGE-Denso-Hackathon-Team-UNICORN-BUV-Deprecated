from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.visual import Florence2VisualDescriber, GeminiVisualDescriber


def test_florence2_visual_describer_returns_a_reviewable_caption():
    class FakeInputs(dict):
        def to(self, *_args, **_kwargs):
            return self

    class FakeProcessor:
        def __call__(self, *, text, images, return_tensors):
            assert text == '<MORE_DETAILED_CAPTION>'
            assert images.size == (3, 2)
            assert return_tensors == 'pt'
            return FakeInputs(input_ids='prompt', pixel_values='pixels')

        def batch_decode(self, generated, *, skip_special_tokens):
            assert generated == ['generated']
            assert skip_special_tokens is False
            return ['<caption>']

        def post_process_generation(self, generated_text, *, task, image_size):
            assert generated_text == '<caption>'
            assert task == '<MORE_DETAILED_CAPTION>'
            assert image_size == (3, 2)
            return {task: 'A machined metal flange with six holes.'}

    class FakeModel:
        def generate(self, **kwargs):
            assert kwargs['input_ids'] == 'prompt'
            assert kwargs['pixel_values'] == 'pixels'
            assert kwargs['max_new_tokens'] == 256
            assert kwargs['do_sample'] is False
            return ['generated']

    describer = Florence2VisualDescriber(
        model='microsoft/Florence-2-base-ft',
        processor=FakeProcessor(),
        model_instance=FakeModel(),
    )

    image = Image.new('RGB', (3, 2), color='white')
    encoded = BytesIO()
    image.save(encoded, format='PNG')

    result = describer.describe_region(
        encoded.getvalue(),
        mime_type='image/png',
        region_ref='#/pictures/1',
        page=2,
    )

    assert result.description == 'A machined metal flange with six holes.'
    assert result.confidence == 0.5
    assert result.review_required is True
    assert 'calibrated confidence' in result.reason


def test_florence2_object_detection_returns_clamped_boxes_and_labels(tmp_path):
    class FakeInputs(dict):
        def to(self, *_args, **_kwargs):
            return self

    class FakeProcessor:
        def __call__(self, *, text, images, return_tensors):
            assert text == '<OD>'
            assert images.size == (10, 8)
            return FakeInputs(input_ids='prompt', pixel_values='pixels')

        def batch_decode(self, generated, *, skip_special_tokens):
            return ['<detections>']

        def post_process_generation(self, _text, *, task, image_size):
            assert task == '<OD>'
            assert image_size == (10, 8)
            return {task: {
                'bboxes': [[-2, 1, 12, 7], [4, 4, 4, 6], [0, 0, float('nan'), 3]],
                'labels': ['forklift', 'empty', 'invalid'],
            }}

    class FakeModel:
        def generate(self, **kwargs):
            assert kwargs['max_new_tokens'] == 512
            return ['generated']

    source = tmp_path / 'safety.png'
    Image.new('RGB', (10, 8), color='white').save(source)
    describer = Florence2VisualDescriber(
        model='microsoft/Florence-2-base-ft',
        processor=FakeProcessor(),
        model_instance=FakeModel(),
    )

    result = describer.detect(source)

    assert (result.image_width, result.image_height) == (10, 8)
    assert [(item.label, item.bbox) for item in result.detections] == [
        ('forklift', (0.0, 1.0, 10.0, 7.0)),
    ]


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
