from hpyx import hpx_hello

def test_say_hpx_hello():
    """Tests the say_hello function"""
    hello_return = hpx_hello()

    assert hello_return == 0
