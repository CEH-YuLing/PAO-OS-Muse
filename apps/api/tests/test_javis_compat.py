from pao.javis_compat import JavisFastPathClassifier, capability_manifest, normalize


def test_normalize_handles_vietnamese_and_whitespace():
    assert normalize('  Xin  chào PAO! ') == 'xin chao pao!'


def test_classifier_allows_simple_self_contained_chat():
    decision = JavisFastPathClassifier().classify('Xin chào trợ lý')
    assert decision.eligible is True
    assert decision.intent_class == 'greeting'


def test_classifier_denies_memory_and_current_data_requests():
    classifier = JavisFastPathClassifier()
    assert classifier.classify('Ghi nhớ doanh thu hôm nay').eligible is False
    assert classifier.classify('Tra cứu số liệu hôm nay').eligible is False


def test_classifier_falls_back_for_attachments_and_long_input():
    classifier = JavisFastPathClassifier()
    assert classifier.classify('Viết lại câu này', has_attachments=True).reason == 'attachment_present'
    assert classifier.classify('a' * 2001).reason == 'objective_too_large'


def test_capability_manifest_tracks_javis_boundaries():
    manifest = capability_manifest()
    assert manifest['fast_path']['source'] == 'Javis fast_path_runtime'
    assert manifest['brain_memory']['target'] == 'pao.memory'
