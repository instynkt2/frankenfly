import numpy as np
from frankenfly.world import World


def test_stimulus_changes_sensory_input_without_teleporting_the_cat():
    world = World()
    world.stimuli.clear()
    uv = np.array([[.5, .75], [.2, .4], [.8, .4]])
    before = world.sense(uv)
    position = (world.x, world.y)
    world.place("light", world.x, world.y)
    assert world.sense(uv)[0] > before[0] + .5
    assert (world.x, world.y) == position
    world.place("odor", world.x, world.y)
    assert world.odor_strength() == 1


def test_no_motor_output_means_no_motion_and_boundaries_block_movement():
    world = World()
    start = (world.x, world.y)
    world.move(0, 0)
    assert (world.x, world.y) == start
    world.x, world.y, world.heading = 935, 100, 0
    world.move(0, 1)
    assert world.x == 936
    assert world.contacts == 1
    world.move(0, 1)
    assert world.contacts == 1


def test_old_stimuli_expire_and_same_kind_replaces_instead_of_accumulates():
    world = World()
    for i in range(50):
        world.place("light", 100+i, 200)
    assert len(world.stimuli) == 1
    world.move(0, 0, dt=46)
    assert world.stimuli == []
