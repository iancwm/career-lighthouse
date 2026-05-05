from services.shared_yaml import Singleton


class ExampleSingleton(Singleton):
    _instance = None
    init_count = 0

    def _init_singleton(self) -> None:
        type(self).init_count += 1
        self.values = []


def test_singleton_mixin_reuses_one_instance_across_constructors():
    ExampleSingleton._instance = None
    ExampleSingleton.init_count = 0

    first = ExampleSingleton()
    second = ExampleSingleton()

    first.values.append("kept")

    assert first is second
    assert second.values == ["kept"]
    assert ExampleSingleton.init_count == 1
