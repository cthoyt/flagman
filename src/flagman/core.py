# -*- coding: utf-8 -*-
"""The core of flagman.

Contains the logic to implement signal handlers and dispatch to user-defined functions.
"""
import signal
from types import FrameType
from typing import Iterable, List, Mapping, MutableSequence, MutableSet

import pkg_resources

from flagman.types import (
    ActionGenerator,
    ActionGeneratorFunction,
    ActionName,
    SignalNumber,
)

HANDLED_SIGNALS: List[signal.Signals] = [signal.SIGUSR1, signal.SIGUSR2, signal.SIGHUP]
SIGNAL_FLAGS: MutableSet[SignalNumber] = set()
KNOWN_ACTIONS: Mapping[ActionName, ActionGeneratorFunction] = {
    action.name: action.load()
    for action in pkg_resources.iter_entry_points('flagman.action')
}
ACTION_BUNDLES: Mapping[SignalNumber, MutableSequence[ActionGenerator]] = {
    signum.value: [] for signum in HANDLED_SIGNALS
}


def create_action_bundles(args_dict: Mapping[str, Iterable[ActionName]]) -> None:
    """Parse the enabled actions and insert them into the global ACTION_BUNDLES mapping.

    The input dictionary should be like `{'usr1': ['action_1_name', 'action_2_name']}`.

    :param args_dict: a mapping of strings to an Iterable of action names
    """
    for signum in HANDLED_SIGNALS:
        action_names = args_dict.get(signum.name.lower()[3:], [])
        actions = [KNOWN_ACTIONS[action_name] for action_name in action_names]
        action_generators = [prime_action_generator(action) for action in actions]
        ACTION_BUNDLES[signum.value].extend(action_generators)


def prime_action_generator(action: ActionGeneratorFunction) -> ActionGenerator:
    """Instantiate an ActionGenerator from an ActionGeneratorFunction.

    Given a function that returns an ActionGenerator, instantiate the generator
    and run the setup code.

    :param action: the ActionGenerator function

    :returns: the primed ActionGenerator
    """
    # instantiate the generator
    action_generator = action()
    # run the setup code
    next(action_generator)

    return action_generator


def set_handlers() -> None:
    """Register handlers for the signals we're interested in.

    Uses the global HANDLED_SIGNALS to decide what signals to register for.

    Danger starts here!
    """
    for signum in HANDLED_SIGNALS:

        def handler(num: int, frame: FrameType) -> None:  # noqa: D403 (capitalization)
            """flagman handler for {}.""".format(signum.name)
            SIGNAL_FLAGS.add(num)

        signal.signal(signum, handler)


def run() -> None:
    """Run the flagman "event loop".

    Waits for a signal to be raised and dispatches to the user-defined handlers
    as appropriate.
    """
    while True:
        signal.pause()
        while SIGNAL_FLAGS:
            try:
                num = SIGNAL_FLAGS.pop()
            except KeyError:
                continue

            actions_to_take = []
            for action_generator in ACTION_BUNDLES[num]:
                actions_to_take.append(action_generator)

            for action in actions_to_take:
                next(action)

            SIGNAL_FLAGS.discard(num)
