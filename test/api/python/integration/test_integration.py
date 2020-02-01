import pytest
import logging

logger = logging.getLogger(__name__)


@pytest.fixture(scope='module')
def env_level():
    return 'singlenode-prvsnr-installed'


@pytest.fixture
def vagrant_default_ssh():
    return True


@pytest.fixture
def env_provider():
    return 'vbox'


@pytest.fixture(params=["py", "cli", "pycli"])
def api_type(request):
    return request.param


def install_provisioner_api(mhost):
    mhost.check_output("pip3 install {}".format(mhost.repo / 'api/python'))


@pytest.fixture
def prepare_test_env(request, hosts_meta):
    # TODO limit to only necessary ones
    for mhost in hosts_meta.values():
        install_provisioner_api(mhost)
        mhost.check_output("pip3 install pytest==5.1.1")  # TODO use requirements or setup.py
        inner_tests_path = mhost.tmpdir / 'test.py'
        mhost.check_output("cp -f {} {}".format(
            mhost.repo / 'test/api/python/integration/test_integration_inner.py', inner_tests_path)
        )
        return inner_tests_path


@pytest.fixture
def run_test(request, api_type):
    def f(mhost, curr_user=None, username=None, password=None, expected_exc=None):
        inner_tests_path = request.getfixturevalue('prepare_test_env')

        script = (
            "TEST_API_TYPE={} pytest -l -q -s --log-cli-level warning --no-print-logs {}::{}"
            .format(api_type, inner_tests_path, request.node.originalname)
        )

        if expected_exc:
            script = "TEST_ERROR={} {}".format(expected_exc, script)

        if username:
            script = (
                "TEST_USERNAME={} TEST_PASSWORD={} {}"
                .format(username, password, script)
            )

            if curr_user:
                script = (
                    "su -l {} -c '{}'"
                    .format(curr_user, script)
                )

        return mhost.check_output(script)

    return f


# TODO
#   - timeout is high because of vbox env build,
#     need to dseparate build logic fromAexplore ways how
#     to separate that (less timeout if env is ready)
# Note. ntpd service doesn't work in docker without additional tricks
# (if it's actually possible)
@pytest.mark.timeout(1200)
@pytest.mark.isolated
@pytest.mark.env_level('singlenode-prvsnr-installed')
@pytest.mark.hosts(['eosnode1'])
def test_ntp_configuration(
    mhosteosnode1, run_test
):
    mhosteosnode1.check_output("yum install -y ntp")
    run_test(mhosteosnode1)
    # TODO
    #   - run ntp.config state and check that nothing changed


@pytest.mark.timeout(1200)
@pytest.mark.skip(reason="EOS-1740")
@pytest.mark.isolated
@pytest.mark.hosts(['eosnode1'])
def test_network_configuration(
    mhosteosnode1, run_test
):
    run_test(mhosteosnode1)


# TODO split to different tests per each test case
@pytest.mark.timeout(1200)
@pytest.mark.isolated
@pytest.mark.hosts(['eosnode1'])
def test_external_auth(
    mhosteosnode1, run_test
):
    username = 'someuser'
    password = '123456'
    group = 'prvsnrusers'  # check for user from default group `prvsnrusers`

    # CASE 1. do not create user at first
    run_test(
        mhosteosnode1, username=username, password=password,
        expected_exc='AuthenticationError'
    )

    # CASE 2. create user but do not add to group for now
    mhosteosnode1.check_output(
        "adduser {0} && echo {1} | passwd --stdin {0}"
        .format(username, password)
    )

    # Note. changing current user actually might be not needed
    # but it's better to cover that case as well
    run_test(
        mhosteosnode1, username=username, password=password,
        expected_exc='AuthorizationError'
    )
    run_test(
        mhosteosnode1, curr_user=username, username=username,
        password=password,
        expected_exc='AuthorizationError'
    )

    # CASE 3. add to group now
    mhosteosnode1.check_output(
        "groupadd {0} && usermod -a -G {0} {1}"
        .format(group, username)
    )
    run_test(mhosteosnode1, username=username, password=password)
    run_test(mhosteosnode1, curr_user=username, username=username, password=password)


@pytest.mark.timeout(1200)
@pytest.mark.isolated
@pytest.mark.hosts(['eosnode1'])
def test_pyinstaller_approach(
    mhosteosnode1, tmpdir_function, request
):
    # Note. python system libarary dir
    # python3 -c 'from distutils.sysconfig import get_python_lib; print(get_python_lib())'

    import inspect

    app_script = (
        """
            import importlib

            import provisioner
            import provisioner.freeze

            pillar = provisioner.pillar_get()
            print(pillar)

            try:
                importlib.import_module('salt')
            except ImportError:
                pass
            else:
                assert False, "salt is available"

            try:
                importlib.import_module('provisioner._api')
            except ImportError:
                pass
            else:
                assert False, "provisioner._api is available"
        """.format(api_path=(mhosteosnode1.repo / 'api/python'))
    )
    app_script = inspect.cleandoc(app_script)

    app_path_local = tmpdir_function / 'myapp.py'
    app_path_local.write_text(app_script)
    app_path_remote = mhosteosnode1.copy_to_host(app_path_local)

    install_provisioner_api(mhosteosnode1)
    mhosteosnode1.check_output("pip3 install pyinstaller")

    mhosteosnode1.check_output(
        "cd {} && pyinstaller {}"
        .format(app_path_remote.parent, app_path_remote.name)
    )

    mhosteosnode1.check_output(
        "{0}/dist/{1}/{1}"
        .format(app_path_remote.parent, app_path_remote.stem)
    )