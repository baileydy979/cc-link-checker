# Standard library
from urllib.parse import urlsplit

# Third-party
from bs4 import BeautifulSoup
import grequests
import pytest

# Local/library specific
import link_checker


@pytest.fixture
def reset_global():
    link_checker.MEMOIZED_LINKS = {}
    link_checker.MAP_BROKEN_LINKS = {}
    return


def test_parse_argument(tmpdir):
    # Test default options
    args = link_checker.parse_argument([])
    assert args.log_level == 30
    assert bool(args.output_errors) is False
    assert args.local is False
    assert args.root_url == "https://creativecommons.org"
    # Test --local
    args = link_checker.parse_argument(["--local"])
    assert args.local is True
    # Test Logging Levels -q/--quiet
    args = link_checker.parse_argument(["-q"])
    assert args.log_level == 40
    args = link_checker.parse_argument(["-qq"])
    assert args.log_level == 50
    args = link_checker.parse_argument(["-qqq"])
    assert args.log_level == 50
    args = link_checker.parse_argument(["-q", "--quiet"])
    assert args.log_level == 50
    # Test Logging Levels -v/--verbose
    args = link_checker.parse_argument(["-v"])
    assert args.log_level == 20
    args = link_checker.parse_argument(["-vv"])
    assert args.log_level == 10
    args = link_checker.parse_argument(["-vvv"])
    assert args.log_level == 10
    args = link_checker.parse_argument(["-v", "--verbose"])
    assert args.log_level == 10
    # Test Logging Levels with both -v and -q
    args = link_checker.parse_argument(["-vq"])
    assert args.log_level == 30
    args = link_checker.parse_argument(["-vvq"])
    assert args.log_level == 20
    args = link_checker.parse_argument(["-vqq"])
    assert args.log_level == 40
    # Test default value of --output-errors
    args = link_checker.parse_argument(["--output-errors"])
    assert bool(args.output_errors) is True
    assert args.output_errors.name == "errorlog.txt"
    # Test custom value of --output-errors
    output_file = tmpdir.join("errorlog.txt")
    args = link_checker.parse_argument(
        ["--output-errors", output_file.strpath]
    )
    assert bool(args.output_errors) is True
    assert args.output_errors.name == output_file.strpath


def test_get_github_licenses():
    all_links = link_checker.get_github_licenses()
    assert len(all_links) > 0


@pytest.mark.parametrize(
    "filename, result",
    [
        # 2 part URL
        (
            "by-nc-nd_2.0",
            "https://creativecommons.org/licenses/by-nc-nd/2.0/legalcode",
        ),
        # 3 part URL
        (
            "by-nc-nd_4.0_cs",
            "https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.cs",
        ),
        # 4 part URL
        (
            "by-nc-nd_3.0_rs_sr-Latn",
            "https://creativecommons.org/licenses/by-nc-nd/3.0/rs/"
            "legalcode.sr-Latn",
        ),
        # Special case - samplingplus
        (
            "samplingplus_1.0",
            "https://creativecommons.org/licenses/sampling+/1.0/legalcode",
        ),
        (
            "samplingplus_1.0_br",
            "https://creativecommons.org/licenses/sampling+/1.0/br/legalcode",
        ),
        # Special case - CC0
        (
            "zero_1.0",
            "https://creativecommons.org/publicdomain/zero/1.0/legalcode",
        ),
    ],
)
def test_create_base_link(filename, result):
    args = link_checker.parse_argument([])
    baseURL = link_checker.create_base_link(args, filename)
    assert baseURL == result


def test_output_write(tmpdir):
    # output_errors is set and written to
    output_file = tmpdir.join("errorlog.txt")
    args = link_checker.parse_argument(
        ["--output-errors", output_file.strpath]
    )
    link_checker.output_write(args, "Output enabled")
    args.output_errors.flush()
    assert output_file.read() == "Output enabled\n"


def test_output_summary(reset_global, tmpdir):
    # output_errors is set and written to
    output_file = tmpdir.join("errorlog.txt")
    args = link_checker.parse_argument(
        ["--output-errors", output_file.strpath]
    )
    link_checker.MAP_BROKEN_LINKS = {
        "https://link1.demo": [
            "https://file1.url/here",
            "https://file2.url/goes/here",
        ],
        "https://link2.demo": ["https://file4.url/here"],
    }
    all_links = ["some link"] * 5
    link_checker.output_summary(args, all_links, 3)
    args.output_errors.flush()
    lines = output_file.readlines()
    i = 0
    assert lines[i] == "\n"
    i += 1
    assert lines[i] == "\n"
    i += 1
    assert lines[i] == "***************************************\n"
    i += 1
    assert lines[i] == "                SUMMARY\n"
    i += 1
    assert lines[i] == "***************************************\n"
    i += 1
    assert lines[i] == "\n"
    i += 1
    assert str(lines[i]).startswith("Timestamp:")
    i += 1
    assert lines[i] == "Total files checked: 5\n"
    i += 1
    assert lines[i] == "Number of error links: 3\n"
    i += 1
    assert lines[i] == "Number of unique broken links: 2\n"
    i += 1
    assert lines[i] == "\n"
    i += 1
    assert lines[i] == "\n"
    i += 1
    assert lines[i] == "Broken link - https://link1.demo found in:\n"
    i += 1
    assert lines[i] == "https://file1.url/here\n"
    i += 1
    assert lines[i] == "https://file2.url/goes/here\n"
    i += 1
    assert lines[i] == "\n"
    i += 1
    assert lines[i] == "Broken link - https://link2.demo found in:\n"
    i += 1
    assert lines[i] == "https://file4.url/here\n"


@pytest.mark.parametrize(
    "link, result",
    [
        # relative links
        ("./license", "https://www.demourl.com/dir1/license"),
        ("../", "https://www.demourl.com/"),
        ("/index", "https://www.demourl.com/index"),
        # append https
        ("//demo.url", "https://demo.url"),
        # absolute link
        ("https://creativecommons.org", "https://creativecommons.org"),
    ],
)
def test_create_absolute_link(link, result):
    base_url = "https://www.demourl.com/dir1/dir2"
    analyze = urlsplit(link)
    res = link_checker.create_absolute_link(base_url, analyze)
    assert res == result


def test_get_scrapable_links():
    args = link_checker.parse_argument([])
    test_file = (
        "<a name='hello'>without href</a>,"
        " <a href='#hello'>internal link</a>,"
        " <a href='mailto:abc@gmail.com'>mailto protocol</a>,"
        " <a href='https://creativecommons.ca'>Absolute link</a>,"
        " <a href='/index'>Relative Link</a>"
    )
    soup = BeautifulSoup(test_file, "lxml")
    test_case = soup.find_all("a")
    base_url = "https://www.demourl.com/dir1/dir2"
    valid_anchors, valid_links, _ = link_checker.get_scrapable_links(
        args, base_url, test_case, None, False
    )
    assert str(valid_anchors) == (
        '[<a href="https://creativecommons.ca">Absolute link</a>,'
        ' <a href="/index">Relative Link</a>]'
    )
    assert (
        str(valid_links)
        == "['https://creativecommons.ca', 'https://www.demourl.com/index']"
    )


def test_exception_handler():
    links_list = [
        "http://invalid-example.creativecommons.org:81",
        "file://C:/Devil",
    ]
    rs = (grequests.get(link, timeout=3) for link in links_list)
    response = grequests.map(
        rs, exception_handler=link_checker.exception_handler
    )
    assert response == ["Connection Error", "Invalid Schema"]


def test_map_links_file(reset_global):
    links = ["link1", "link2", "link1"]
    file_urls = ["file1", "file1", "file3"]
    for idx, link in enumerate(links):
        file_url = file_urls[idx]
        link_checker.map_links_file(link, file_url)
    assert link_checker.MAP_BROKEN_LINKS == {
        "link1": ["file1", "file3"],
        "link2": ["file1"],
    }


def test_write_response(tmpdir):
    # Set config
    output_file = tmpdir.join("errorlog.txt")
    args = link_checker.parse_argument(
        ["--output-errors", output_file.strpath]
    )

    # Text to extract valid_anchors
    text = (
        "<a href='http://httpbin.org/status/200'>Response 200</a>,"
        " <a href='file://link3'>Invalid Scheme</a>,"
        " <a href='http://httpbin.org/status/400'>Response 400</a>"
    )
    soup = BeautifulSoup(text, "lxml")
    valid_anchors = soup.find_all("a")

    # Setup function params
    all_links = [
        "http://httpbin.org/status/200",
        "file://link3",
        "http://httpbin.org/status/400",
    ]
    rs = (grequests.get(link) for link in all_links)
    response = grequests.map(
        rs, exception_handler=link_checker.exception_handler
    )
    base_url = "https://baseurl/goes/here"
    license_name = "by-cc-nd_2.0"

    # Set output to external file
    caught_errors = link_checker.write_response(
        args,
        all_links,
        response,
        base_url,
        license_name,
        valid_anchors,
        license_name,
        False,
    )
    assert caught_errors == 2
    args.output_errors.flush()
    lines = output_file.readlines()
    i = 0
    assert lines[i] == "\n"
    i += 1
    assert lines[i] == "by-cc-nd_2.0\n"
    i += 1
    assert lines[i] == "URL: https://baseurl/goes/here\n"
    i += 1
    assert lines[i] == f'  {"Invalid Schema":<24}file://link3\n'
    i += 1
    assert lines[i] == f'{"":<26}<a href="file://link3">Invalid Scheme</a>\n'
    i += 1
    assert lines[i] == f'  {"400":<24}http://httpbin.org/status/400\n'
    i += 1
    assert lines[i] == (
        f'{"":<26}<a href="http://httpbin.org/status/400">Response 400</a>\n'
    )


def test_get_memoized_result(reset_global):
    text = (
        "<a href='link1'>Link 1</a>,"
        " <a href='link2'>Link 2</a>,"
        " <a href='link3_stored'>Link3 - stored</a>,"
        " <a href='link4_stored'>Link4 - stored</a>"
    )
    soup = BeautifulSoup(text, "lxml")
    valid_anchors = soup.find_all("a")
    valid_links = ["link1", "link2", "link3_stored", "link4_stored"]
    link_checker.MEMOIZED_LINKS = {"link3_stored": 200, "link4_stored": 404}
    (
        stored_links,
        stored_anchors,
        stored_result,
        check_links,
        check_anchors,
    ) = link_checker.get_memoized_result(valid_links, valid_anchors)
    assert stored_links == ["link3_stored", "link4_stored"]
    assert str(stored_anchors) == (
        '[<a href="link3_stored">Link3 - stored</a>,'
        ' <a href="link4_stored">Link4 - stored</a>]'
    )
    assert stored_result == [200, 404]
    assert check_links == ["link1", "link2"]
    assert (
        str(check_anchors)
        == '[<a href="link1">Link 1</a>, <a href="link2">Link 2</a>]'
    )


def test_memoize_result(reset_global):
    check_links = [
        # Good response
        "https://httpbin.org/status/200",
        # Bad response
        "https://httpbin.org/status/400",
        # Invalid schema - Caught by exception handler
        "file://hh",
    ]
    rs = (grequests.get(link, timeout=1) for link in check_links)
    response = grequests.map(
        rs, exception_handler=link_checker.exception_handler
    )
    link_checker.memoize_result(check_links, response)
    assert len(link_checker.MEMOIZED_LINKS.keys()) == 3
    assert (
        link_checker.MEMOIZED_LINKS[
            "https://httpbin.org/status/200"
        ].status_code
        == 200
    )
    assert (
        link_checker.MEMOIZED_LINKS[
            "https://httpbin.org/status/400"
        ].status_code
        == 400
    )
    assert link_checker.MEMOIZED_LINKS["file://hh"] == "Invalid Schema"


@pytest.mark.parametrize(
    "URL, error",
    [
        ("https://www.google.com:82", "Timeout"),
        ("http://doesnotexist.google.com", "ConnectionError"),
    ],
)
def test_request_text(URL, error):
    with pytest.raises(link_checker.CheckerError) as e:
        assert link_checker.request_text(URL)
        assert str(e.value) == (
            "FAILED to retreive source HTML (https://www.google.com:82) due"
            " to {}".format(error)
        )


def test_request_local_text():
    random_string = "creativecommons cc-link-checker"
    with open("test_file.txt", "w") as test_file:
        test_file.write(random_string)
        test_file.close
    # Change local path to current directory
    link_checker.LICENSE_LOCAL_PATH = "./"
    assert link_checker.request_local_text("test_file.txt") == random_string


# TODO: Optimize the test using mock
@pytest.mark.parametrize(
    "errors_total, map_links",
    [(3, {"link1": ["file1", "file3"], "link2": ["file1"]}), (0, {})],
)
def test_output_test_summary(errors_total, map_links, reset_global, tmpdir):
    link_checker.MAP_BROKEN_LINKS = map_links
    link_checker.output_test_summary(errors_total)
    with open("test-summary/junit-xml-report.xml", "r") as test_summary:
        if errors_total != 0:
            test_summary.readline()
            test_summary.readline()
            test_summary.readline()
            test_summary.readline()

            # The following is split up because sometimes message= is first and
            # sometimes type= is first (ex. local macOS dev versus GitHub
            # Actions Linux)
            test_line = test_summary.readline()
            assert test_line.startswith("\t\t\t<failure")
            assert 'message="3 broken links found"' in test_line
            assert 'type="failure"' in test_line
            assert test_line.endswith(">Number of error links: 3\n")

            assert (
                test_summary.readline()
                == "Number of unique broken links: 2</failure>\n"
            )
