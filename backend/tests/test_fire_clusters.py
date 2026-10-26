from app.services import fire_clusters as fc

T = 1_792_000_000


def pt(lat, lng, mw=10.0, seen=T, n=1):
    return [lat, lng, mw, seen, n]


def test_locates_provinces_and_peatland_from_the_baked_shapes():
    which, peat = fc.locate([0.6, -2.3, -3.3, 1.0, 1.55], [102.4, 114.0, 104.6, 104.0, 110.35])
    names = [fc.provinces()[i]["name"] if i is not None else None for i in which]

    assert names == ["Riau", "Central Kalimantan", "South Sumatra", None, "Sarawak"]
    assert list(peat) == [True, True, False, False, False]


def test_touching_detections_join_one_named_cluster_with_stats():
    points = [
        pt(-2.30, 114.00, 40, T, 3),
        pt(-2.40, 114.10, 20, T + 3600, 1),  # next cell: same fire area
        pt(-2.20, 114.25, 5, T + 7200, 2),
        pt(0.60, 102.40, 15, T, 1),  # Riau, far away
    ]
    ids, clusters = fc.cluster_points(points)

    assert ids[0] == ids[1] == ids[2] != ids[3]
    kal = clusters[ids[0]]
    assert kal["province"] == "Central Kalimantan" and kal["country"] == "Indonesia"
    assert kal["detections"] == 6
    assert kal["frp_mw"] == 65.0
    assert (kal["first"], kal["last"]) == (T, T + 7200)
    assert kal["peat_share"] == 1.0
    assert kal["bbox"] == [114.0, -2.4, 114.25, -2.2]
    # Strongest cluster first.
    assert clusters[0]["id"] == 0 and clusters[0]["frp_mw"] >= clusters[1]["frp_mw"]


def test_a_cluster_across_a_border_splits_by_province_and_sea_is_unnamed():
    # Riau and Jambi meet near 1.05S at 102.5E: touching cells on both sides.
    which, _ = fc.locate([-0.95, -1.15], [102.5, 102.5])
    assert which[0] != which[1]
    ids, clusters = fc.cluster_points([pt(-0.95, 102.5), pt(-1.15, 102.5), pt(0.0, 108.0)])

    assert len({ids[0], ids[1]}) == 2
    assert {clusters[ids[0]]["province"], clusters[ids[1]]["province"]} == {"Riau", "Jambi"}
    assert clusters[ids[2]]["province"] is None


def test_no_points_no_clusters():
    assert fc.cluster_points([]) == ([], [])
