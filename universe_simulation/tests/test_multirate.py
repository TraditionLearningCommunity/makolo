from universe_sim.simulation.multirate import CadenceEvolution, OrdonnanceurMultiTaux


def test_scheduler_merges_common_coordinate_time_deadlines():
    scheduler = OrdonnanceurMultiTaux()
    scheduler.ajouter(CadenceEvolution("local", 60))
    scheduler.ajouter(CadenceEvolution("galactic", 300))
    plan = scheduler.planifier(600)
    assert [e.offset_s for e in plan] == [60, 120, 180, 240, 300, 360, 420, 480, 540, 600]
    at300 = next(e for e in plan if e.offset_s == 300)
    assert {s.nom for s in at300.evolutions} == {"local", "galactic"}
    assert plan[-1].barriere_synchronisation


def test_final_barrier_adds_partial_steps_without_extending_duration():
    scheduler = OrdonnanceurMultiTaux(
        {"fast": CadenceEvolution("fast", 30), "slow": CadenceEvolution("slow", 100)}
    )
    plan = scheduler.planifier(250)
    final = plan[-1]
    assert final.offset_s == 250
    by_name = {s.nom: s for s in final.evolutions}
    assert by_name["fast"].dt_s == 10
    assert by_name["fast"].partiel
    assert by_name["slow"].dt_s == 50
    assert by_name["slow"].partiel


def test_phase_changes_first_due_time_only():
    scheduler = OrdonnanceurMultiTaux({"sensor": CadenceEvolution("sensor", 10, phase_s=2)})
    plan = scheduler.planifier(25)
    assert [e.offset_s for e in plan] == [2, 12, 22, 25]
    assert plan[-1].evolutions[0].dt_s == 3


def test_invalid_cadence_is_rejected():
    try:
        CadenceEvolution("bad", 0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid cadence rejection")
