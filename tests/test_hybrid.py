from copy import deepcopy
import pytest
from app.rendering import hybrid


def plan():
    return {'background':{'background_id':'orchard','identity_hash':'source'},
            'direction':[{'kind':'action','actors':{'nabil':{'action':'walk'}}}]}


def test_prototype_requires_explicit_request(monkeypatch):
    calls=[]
    def environment(bid,prototype=False):
        calls.append(prototype)
        return {'background_identity':'source'} if prototype else None
    monkeypatch.setattr(hybrid,'environment',environment)
    automatic=plan();assert hybrid.resolve_mode(automatic)=={}
    assert automatic['effective_render_mode']=='2d' and calls==[False]
    explicit={**plan(),'render_mode':'hybrid_2_5d','allow_hybrid_prototype':True}
    assert hybrid.resolve_mode(explicit) and explicit['effective_render_mode']=='hybrid_2_5d'


def test_mismatched_or_mixed_environment_keeps_entire_episode_flat(monkeypatch):
    monkeypatch.setattr(hybrid,'environment',lambda bid,*args:{'background_identity':'source'} if bid=='orchard' else None)
    mixed=plan();mixed['backgrounds']={'orchard':mixed['background'],'station':{'identity_hash':'station-source'}}
    assert hybrid.resolve_mode(mixed)=={} and mixed['effective_render_mode']=='2d'
    changed=plan();changed['background']['identity_hash']='changed'
    assert hybrid.resolve_mode(changed)=={}
    explicit=plan();explicit['background']['identity_hash']='changed';explicit['render_mode']='hybrid_2_5d'
    with pytest.raises(ValueError):hybrid.resolve_mode(explicit)


def test_dialogue_only_does_not_need_hybrid(monkeypatch):
    monkeypatch.setattr(hybrid,'environment',lambda *args:pytest.fail('No environment needed for dialogue-only fallback'))
    p=plan();p['direction']=[{'kind':'speech','actors':{'nabil':{'action':'talk'}}}]
    assert hybrid.resolve_mode(p)=={} and p['effective_render_mode']=='2d'


def test_spatial_placement_preserves_grounding_and_rejects_collision():
    direction=[{'background_id':'orchard','visible_characters':['nabil','rayan','anika'],
        'actors':{c:{'from_x':0,'to_x':20} for c in ('nabil','rayan','anika')},'camera':{'shot':'wide'}}]
    env={'orchard':{'environment_id':'depth','actor_depths':[-.12,.12,-.05],'blocked_zones':[]}}
    original=deepcopy(direction);result=hybrid.spatial_direction(direction,720,env)
    assert direction==original
    for actor in result[0]['spatial']['actors'].values():
        assert actor['position_from'][1]==actor['position_to'][1]==actor['ground_y']==0
        assert actor['position_from'][2]==actor['position_to'][2]
        assert actor['position_to'][0]-actor['position_from'][0]==pytest.approx(.2)
    env['orchard']['blocked_zones']=[[-2.4,-.12,.5]]
    with pytest.raises(ValueError,match='intersects'):hybrid.spatial_direction(direction,720,env)
