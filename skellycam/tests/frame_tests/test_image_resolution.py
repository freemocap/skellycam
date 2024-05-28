from skellycam.core.detection.image_resolution import ImageResolution


def test_image_resolution_from_string(image_resolution_fixture: ImageResolution):
    og_width = image_resolution_fixture.width
    og_height = image_resolution_fixture.height
    default_delimited_resolution = ImageResolution.from_string(f"{og_height}x{og_width}")
    assert default_delimited_resolution.width == og_width
    assert default_delimited_resolution.height == og_height

    comma_delimited_resolution = ImageResolution.from_string(f"({og_height}, {og_height})", delimiter=",")
    assert comma_delimited_resolution.width == og_height
    assert comma_delimited_resolution.height == og_height


def test_image_resolution_orientation(image_resolution_fixture: ImageResolution):
    if image_resolution_fixture.width > image_resolution_fixture.height:
        assert image_resolution_fixture.orientation == "landscape"

    if image_resolution_fixture.width < image_resolution_fixture.height:
        assert image_resolution_fixture.orientation == "portrait"

    if image_resolution_fixture.width == image_resolution_fixture.height:
        assert image_resolution_fixture.orientation == "square"


def test_image_resolution_aspect_ratio(image_resolution_fixture: ImageResolution):
    assert image_resolution_fixture.aspect_ratio == image_resolution_fixture.width / image_resolution_fixture.height


def test_image_resolution_comparison(image_resolution_fixture: ImageResolution):
    half_resolution = ImageResolution(width=image_resolution_fixture.width // 2,
                                      height=image_resolution_fixture.height // 2)
    assert half_resolution < image_resolution_fixture


def test_image_resolution_equality():
    resolution1 = ImageResolution(width=1920, height=1080)
    resolution2 = ImageResolution(width=1920, height=1080)
    assert resolution1 == resolution2
    resolution3 = ImageResolution(width=1280, height=720)
    assert resolution1 != resolution3
