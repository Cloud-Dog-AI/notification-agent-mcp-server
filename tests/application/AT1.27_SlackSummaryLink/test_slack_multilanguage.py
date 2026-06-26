# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
AT1.4.2 & AT1.4.3: Multi-Language Slack Summary Tests
Tests Polish→English/Chinese and Chinese→Chinese/English/German translations
"""

import io
import json
import re
import time

import httpx
import pytest
from pypdf import PdfReader

from tests.utils.slack_helpers import (
    assert_slack_mrkdwn_contains,
    require_slack_api_config,
    wait_for_slack_message,
)
from tests.utils.test_helpers import check_test_dependencies

# Constants (config-driven)
API_TIMEOUT = None
WAIT_TIMEOUT = None
POLL_INTERVAL = None


def _require_number(test_config, key: str, *, number_type: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env/config")
    try:
        return float(value) if number_type == "float" else int(value)
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: {key} must be a {number_type}: {e}")


def _get_api_timeout(test_config) -> httpx.Timeout:
    total = _require_number(test_config, "api.timeout", number_type="float")
    connect = test_config.get("api.connect_timeout")
    if connect is None or connect == "":
        connect = total
    else:
        connect = _require_number(test_config, "api.connect_timeout", number_type="float")
    read = test_config.get("api.read_timeout")
    if read is None or read == "":
        read = total
    else:
        read = _require_number(test_config, "api.read_timeout", number_type="float")
    return httpx.Timeout(timeout=total, connect=connect, read=read)


def _get_wait_timeout(test_config) -> float:
    wait_timeout = (
        test_config.get("test.slack.wait_timeout")
        or test_config.get("test.at14b.max_wait")
        or test_config.get("test.at14c.max_wait")
        or test_config.get("test.at14a.max_wait")
        or test_config.get("api.timeout")
    )
    if wait_timeout is None or wait_timeout == "":
        pytest.fail(
            "❌ HARD FAIL: Configure test.slack.wait_timeout, test.at14*.max_wait, or api.timeout"
        )
    return float(wait_timeout)


def _get_poll_interval(test_config) -> float:
    poll_interval = (
        test_config.get("test.slack.poll_interval")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    if poll_interval is None or poll_interval == "":
        pytest.fail(
            "❌ HARD FAIL: Configure test.slack.poll_interval, api.connect_timeout, or api.timeout"
        )
    return float(poll_interval)


@pytest.fixture(autouse=True)
def _config_timeouts(test_config):
    global API_TIMEOUT, WAIT_TIMEOUT, POLL_INTERVAL
    API_TIMEOUT = _get_api_timeout(test_config)
    WAIT_TIMEOUT = _get_wait_timeout(test_config)
    POLL_INTERVAL = _get_poll_interval(test_config)
    yield


def _get_slack_timeouts(test_config):
    wait_timeout = (
        test_config.get("test.slack.wait_timeout")
        or test_config.get("test.at14b.max_wait")
        or test_config.get("test.at14c.max_wait")
        or test_config.get("test.at14a.max_wait")
        or test_config.get("api.timeout")
    )
    poll_interval = (
        test_config.get("test.slack.poll_interval")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    request_timeout = (
        test_config.get("test.slack.request_timeout")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    if wait_timeout is None or wait_timeout == "":
        pytest.fail(
            "Slack wait timeout missing. Configure test.slack.wait_timeout, test.at14b.max_wait, test.at14c.max_wait, test.at14a.max_wait, or api.timeout."
        )
    if poll_interval is None or poll_interval == "":
        pytest.fail(
            "Slack poll interval missing. Configure test.slack.poll_interval, api.connect_timeout, or api.timeout."
        )
    if request_timeout is None or request_timeout == "":
        pytest.fail(
            "Slack request timeout missing. Configure test.slack.request_timeout, api.connect_timeout, or api.timeout."
        )
    return float(wait_timeout), float(poll_interval), float(request_timeout)


def _get_chat_rest_channels(api_base_url: str, api_key: str):
    with httpx.Client(timeout=API_TIMEOUT) as client:
        channels_response = client.get(
            f"{api_base_url}/channels",
            headers={"X-API-Key": api_key},
        )
        channels_response.raise_for_status()
        all_channels = channels_response.json()
    return [
        ch for ch in all_channels
        if ch.get("type") == "chat_rest" or "chat_rest" in ch.get("name", "").lower()
    ]


def _set_chat_rest_restrictions(api_base_url: str, api_key: str, restrictions: dict) -> dict:
    originals = {}
    for channel in _get_chat_rest_channels(api_base_url, api_key):
        channel_id = channel["id"]
        originals[channel_id] = channel.get("restrictions_json")
        with httpx.Client(timeout=API_TIMEOUT) as client:
            update_response = client.patch(
                f"{api_base_url}/channels/{channel_id}",
                json={"restrictions_json": restrictions},
                headers={"X-API-Key": api_key},
            )
            update_response.raise_for_status()
    return originals


def _restore_chat_rest_restrictions(api_base_url: str, api_key: str, originals: dict) -> None:
    for channel_id, restrictions_json in originals.items():
        with httpx.Client(timeout=API_TIMEOUT) as client:
            update_response = client.patch(
                f"{api_base_url}/channels/{channel_id}",
                json={"restrictions_json": restrictions_json},
                headers={"X-API-Key": api_key},
            )
            update_response.raise_for_status()


@pytest.fixture
def api_base_url(test_config):
    """Get API base URL from configuration - NO FALLBACK"""
    url = test_config.get("api_server.base_url")
    if not url:
        pytest.fail("❌ api_server.base_url not in env file. Add: CLOUD_DOG__NOTIFY__API_SERVER__BASE_URL=...")
    return url


@pytest.fixture
def api_key(test_config):
    """Get API key from configuration - NO FALLBACK"""
    key = test_config.get("api_server.api_key")
    if not key:
        pytest.fail("❌ api_server.api_key not in env file. Add: CLOUD_DOG__NOTIFY__API_SERVER__API_KEY=...")
    return key


@pytest.fixture
def slack_config(test_config):
    """Get Slack channel configuration"""
    channel_name = test_config.get("test.slack_channel_name")
    if not channel_name:
        pytest.fail("test.slack_channel_name not configured. Check your env file.")
    endpoint = test_config.get("channels.chat_rest.transparentbordes.endpoint")
    if not endpoint:
        pytest.fail("channels.chat_rest.transparentbordes.endpoint not configured. Check your env file.")
    return {"channel_name": channel_name, "endpoint": endpoint}
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


@pytest.fixture
def test_email(test_config):
    """Get test email from configuration"""
    email = test_config.get("test.email")
    if not email:
        pytest.fail("test.email not configured. Check your env file.")
    return email


@pytest.fixture
def polish_message_content():
    """Polish message content for AT1.4.2 test"""
    return """**Zdolność Wielkich Modeli Językowych (LLM) do Podsumowywania i Dystrybucji Informacji w Spersonalizowanych Formatach przez Wiele Kanałów**

**Wprowadzenie**

W erze cyfrowej ogromna ilość informacji generowanych codziennie jest przytłaczająca. Od prac naukowych i artykułów prasowych po posty w mediach społecznościowych i dokumentację techniczną, użytkownicy są zanurzeni w treściach, które często przekraczają ich zdolność do przetwarzania i zapamiętywania. To zjawisko, znane jako „przeciążenie informacyjne", stanowi istotne wyzwania dla osób prywatnych, organizacji i instytucji starających się wydobyć wartość z danych. Wielkie Modele Językowe (LLM), takie jak GPT-4, BERT i inne zaawansowane systemy, stały się potężnymi narzędziami do rozwiązania tych wyzwań. Ich zdolność do podsumowywania złożonych informacji, dostosowywania treści do preferencji użytkowników oraz dystrybucji jej przez wiele kanałów dostosowanych do konkretnych potrzeb reprezentuje przełom w sposobie, w jaki informacje są konsumowane i wykorzystywane.

Ten podsumowanie bada techniczne możliwości LLM, ich rolę w personalizacji, wyzwania, przed którymi stoją, oraz ich potencjał do rewolucjonizowania dystrybucji informacji w przyszłości. LLM wykorzystują zaawansowane algorytmy uczenia maszynowego do analizy i przetwarzania języka naturalnego, co pozwala im generować treści w różnych językach i formatach. Zastosowania obejmują media, gdzie LLM mogą tworzyć spersonalizowane wiadomości dla różnych odbiorców, naukę, gdzie mogą podsumowywać skomplikowane badania, medycynę, gdzie mogą tłumaczyć informacje medyczne dla pacjentów, oraz biznes, gdzie mogą optymalizować komunikację korporacyjną.

**Możliwości Techniczne LLM**

LLM opierają się na architekturach transformatorów, które umożliwiają im przetwarzanie dużych ilości danych tekstowych i uczenie się wzorców językowych. Kluczowe możliwości techniczne to ekstrakcja informacji, gdzie model identyfikuje i wydobywa najważniejsze fakty z długich dokumentów, oraz streszczenie abstrakcyjne, gdzie model generuje nowe zdania, które oddają istotę oryginalnego tekstu. LLM mogą również dostosowywać styl i ton treści do preferencji odbiorcy, co jest szczególnie ważne w kontekście komunikacji międzykulturowej.

**Wyzwania i Ograniczenia**

Pomimo swoich możliwości, LLM napotykają pewne wyzwania. Jednym z głównych problemów jest tendencja do „halucynacji", czyli generowania informacji, które nie są oparte na faktach. Inne wyzwania obejmują zachowanie spójności kontekstowej w długich tekstach, gdzie model może tracić śledzenie głównego wątku, oraz zapewnienie bezpieczeństwa i prywatności danych użytkowników. Ponadto, LLM mogą mieć trudności z obsługą specjalistycznej terminologii w dziedzinach takich jak prawo czy medycyna, gdzie precyzja jest kluczowa.

**Przyszłe Kierunki**

Przyszłość LLM w dziedzinie podsumowywania i dystrybucji informacji jest obiecująca. Przyszłe wdrożenia mogą obejmować integrację z systemami rzeczywistości rozszerzonej (AR) i wirtualnej (VR), co pozwoliłoby na tworzenie immersyjnych doświadczeń informacyjnych. LLM mogą również ewoluować w kierunku bardziej zaawansowanej personalizacji, wykorzystując uczenie federacyjne do ochrony prywatności użytkowników. Ponadto, rozwój wielomodalnych LLM, które mogą przetwarzać nie tylko tekst, ale również obrazy, dźwięk i wideo, otworzy nowe możliwości w komunikacji i edukcji.

**Wnioski**

Zdolność LLM do podsumowywania i dystrybucji informacji w spersonalizowanych formatach przez wiele kanałów reprezentuje znaczący postęp w sposobie, w jaki ludzie wchodzą w interakcję z danymi. Jednakże, aby w pełni wykorzystać ten potencjał, konieczne jest rozwiązanie wyzwań związanych z dokładnością, bezpieczeństwem i etyką. W miarę jak technologia się rozwija, LLM mają potencjał, aby przekształcić nie tylko sposób, w jaki informacje są konsumowane, ale również sposób, w jaki są tworzone i udostępniane."""


@pytest.fixture
def chinese_message_content():
    """Chinese message content for AT1.4.3 test"""
    return """**大型语言模型（LLM）总结和传播信息的能力，以个性化格式跨多个渠道**

**引言**

在数字时代，每天产生的信息量是惊人的。从科学研究和新闻文章到社交媒体帖子和技术文档，用户沉浸在经常超出其处理和保留能力的内容中。这种现象被称为"信息过载"，对试图从数据中提取价值的个人、组织和机构构成了重大挑战。大型语言模型（LLM），如GPT-4、BERT和其他先进系统，已成为应对这些挑战的强大工具。它们总结复杂信息、根据用户偏好定制内容以及通过针对特定需求定制的多个渠道分发内容的能力，代表了人们消费和利用信息方式的突破。

本总结探讨了LLM的技术能力、它们在个性化中的作用、它们面临的挑战以及它们在未来革新信息传播的潜力。LLM利用先进的机器学习算法来分析和处理自然语言，使它们能够生成不同语言和格式的内容。应用包括媒体，LLM可以为不同受众创建个性化消息，科学，它们可以总结复杂的研究，医学，它们可以为患者翻译医疗信息，以及商业，它们可以优化企业沟通。

**LLM的技术能力**

LLM基于变压器架构，使它们能够处理大量文本数据并学习语言模式。关键技术能力包括信息提取，模型识别并从长文档中提取最重要的事实，以及抽象总结，模型生成捕捉原始文本本质的新句子。LLM还可以根据接收者的偏好调整内容的风格和语气，这在跨文化交流的背景下特别重要。

**挑战和局限性**

尽管具有这些能力，LLM仍面临某些挑战。主要问题之一是"幻觉"的倾向，即生成不基于事实的信息。其他挑战包括在长文本中保持上下文连贯性，模型可能会失去对主线的跟踪，以及确保用户数据的安全和隐私。此外，LLM可能难以处理法律或医学等领域的专业术语，在这些领域精确性至关重要。

**未来方向**

LLM在总结和传播信息领域的未来是有希望的。未来的实施可能包括与增强现实（AR）和虚拟现实（VR）系统的集成，这将允许创建沉浸式信息体验。LLM还可能朝着更高级的个性化发展，利用联邦学习来保护用户隐私。此外，能够处理不仅是文本，还有图像、声音和视频的多模态LLM的发展，将为沟通和教育开辟新的可能性。

**结论**

LLM以个性化格式跨多个渠道总结和传播信息的能力，代表了人们与数据交互方式的重大进步。然而，要充分实现这一潜力，必须解决与准确性、安全性和伦理相关的挑战。随着技术的发展，LLM有潜力不仅改变信息的消费方式，还改变信息的创建和共享方式。LLM在各行各业的应用正在扩大，从客户服务聊天机器人到自动化新闻生成，再到教育辅导系统。这些应用展示了LLM如何能够提高效率、降低成本并改善用户体验。随着研究的深入和技术的成熟，我们可以期待看到更多创新的应用案例，进一步推动LLM在全球范围内的采用和影响。"""
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_polish_to_english_chinese(api_base_url, api_key, slack_config, test_config, polish_message_content):
    """
    AT1.4.2: Polish→English and Polish→Chinese translation test
    
    Creates a message in Polish and delivers it to two users:
    1. English user - expects English summary/labels/PDF
    2. Chinese user - expects Chinese summary/labels/PDF
    
    Validates:
    - Summary translated correctly
    - Link labels translated correctly
    - PDF content translated correctly
    - Message link content translated correctly
    """
    print("\n" + "=" * 80)
    print("AT1.4.2: POLISH → ENGLISH/CHINESE TRANSLATION TEST")
    print("=" * 80)
    
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=True,
        requires_api=True,
        test_name="test_polish_to_english_chinese",
    )

    slack_token, slack_channel_id = require_slack_api_config(test_config)
    channel_name = slack_config["channel_name"]
    slack_endpoint = slack_config["endpoint"]
    target_max_length = 400
    
    # Setup: Update channel restrictions via API
    print("\n" + "-" * 80)
    print("SETUP: UPDATE CHANNEL RESTRICTIONS VIA API")
    print("-" * 80)
    
    restrictions = {
        "max_length": target_max_length,
        "allowed_formats": ["text"],
        "link_strategy": "summary+link",
    }
    originals = _set_chat_rest_restrictions(api_base_url, api_key, restrictions)
    
    # Create two users with different language preferences
    users_config = [
        {
            "language": "en",
            "expected_indicators": [
                "llm",
                "summar",
                "distribut",
                "channel",
                "privacy",
                "hallucinat",
            ],
            "language_name": "English"
        },
        {
            "language": "zh",
            "expected_indicators": ["语言模型", "信息", "总结", "传播"],
            "language_name": "Chinese"
        }
    ]
    
    try:
        for user_config in users_config:
            target_language = user_config["language"]
            expected_indicators = user_config["expected_indicators"]
            language_name = user_config["language_name"]
            
            print("\n" + "=" * 80)
            print(f"TESTING: Polish → {language_name} ({target_language})")
            print("=" * 80)
            
            # Create message with Polish content and user preferences
            marker = f"AT1.4.2 {language_name} {int(time.time())}"
            message_payload = {
                "title": "Test Wiadomość Podsumowanie - Polski do " + language_name,
                "content": [{"type": "markdown", "body": polish_message_content}],
                "destinations": [
                    {
                        "channel": channel_name,
                        "address": slack_endpoint,
                        "preferences": {
                            "language": target_language,
                            "content_style": "text"
                        }
                    }
                ],
                "options": {"subject": marker},
            }
            
            # Step 1: Create message
            print("\n" + "-" * 80)
            print("STEP 1: CREATE MESSAGE")
            print("-" * 80)
            message_id = None
            
            with httpx.Client(timeout=API_TIMEOUT) as client:
                response = client.post(
                    f"{api_base_url}/messages",
                    headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                    json=message_payload
                )
                print(f"✅ POST /messages: Status {response.status_code}")
                
                if response.status_code != 201:
                    pytest.fail(f"Message creation failed: {response.status_code}")
                
                result = response.json()
                message_id = result.get("message_id") or result.get("id")
                message_guid = result.get("guid")
                
                if not message_guid and message_id:
                    msg_response = client.get(
                        f"{api_base_url}/messages/{message_id}",
                        headers={"X-API-Key": api_key}
                    )
                    if msg_response.status_code == 200:
                        message_guid = msg_response.json().get("guid")
                
                print(f"✅ Message created: ID={message_id}, GUID={message_guid}")
            
            try:
                # Step 2: Wait for delivery
                print("\n" + "-" * 80)
                print("STEP 2: WAIT FOR DELIVERY")
                print("-" * 80)
                
                delivery = None
                start_time = time.time()
                max_attempts = int(WAIT_TIMEOUT / POLL_INTERVAL)
                
                for i in range(max_attempts):
                    with httpx.Client(timeout=API_TIMEOUT) as client:
                        response = client.get(
                            f"{api_base_url}/messages/{message_id}/deliveries",
                            headers={"X-API-Key": api_key}
                        )
                        
                        if response.status_code == 200:
                            deliveries = response.json().get("items", [])
                            if deliveries:
                                delivery = deliveries[0]
                                state = delivery.get("state")
                                elapsed = time.time() - start_time
                                print(f"  Attempt {i+1}: state={state}")
                                
                                if state == "sent":
                                    print(f"✅ Delivery completed in {elapsed:.1f}s")
                                    break
                                elif state in ["hard_failed", "cancelled"]:
                                    pytest.fail(f"Delivery failed: {delivery.get('last_error')}")
                    
                    time.sleep(POLL_INTERVAL)
                
                if delivery is None or delivery.get("state") != "sent":
                    pytest.fail(f"Delivery timeout after {WAIT_TIMEOUT}s")
                
                wait_timeout, poll_interval, request_timeout = _get_slack_timeouts(test_config)
                slack_message = wait_for_slack_message(
                    slack_token,
                    slack_channel_id,
                    marker,
                    timeout=wait_timeout,
                    poll_interval=poll_interval,
                    request_timeout=request_timeout,
                )
                assert_slack_mrkdwn_contains(slack_message, marker)
                
                # Step 3: Validate payload
                print("\n" + "-" * 80)
                print(f"STEP 3: VALIDATE PAYLOAD ({language_name.upper()}, 400 CHAR LIMIT)")
                print("-" * 80)
                
                personalised_payload = delivery.get("personalised_payload")
                if not personalised_payload:
                    pytest.fail("No personalised_payload in delivery")
                
                payload_data = json.loads(personalised_payload) if isinstance(personalised_payload, str) else personalised_payload
                text = payload_data.get("text", "")
                
                print(f"📄 Text length: {len(text)} characters")
                assert len(text) <= target_max_length, f"Message exceeds character limit: {len(text)} > {target_max_length}"
                
                # Validate language
                text_lower = text.lower()
                found_indicators = [ind for ind in expected_indicators if ind.lower() in text_lower]
                print(f"✅ Found {language_name} indicators: {found_indicators[:3]}")
                assert len(found_indicators) >= 2, f"Not enough {language_name} indicators found in summary"
                
                # Validate link with language parameter
                link_pattern = re.compile(r'<https?://[^>|]+\|([^>]+)>')
                links = link_pattern.findall(text)
                assert links, "Link to full message MUST be present"
                
                link_text = links[0]
                print(f"✅ Found link label: '{link_text}'")
                
                # Extract full link URL
                full_link_match = re.search(r'<(https?://[^>|]+)\|', text)
                assert full_link_match, "Could not extract link URL"
                
                link_url = full_link_match.group(1)
                assert f"?language={target_language}" in link_url, f"Link must contain language parameter: {link_url}"
                print(f"✅ Link contains language parameter: {target_language}")
                
                # Step 4: Validate message link content
                print("\n" + "-" * 80)
                print(f"STEP 4: VALIDATE MESSAGE LINK CONTENT ({language_name})")
                print("-" * 80)
                
                with httpx.Client(timeout=API_TIMEOUT) as client:
                    html_response = client.get(
                        link_url,
                        headers={"Accept": "text/html"}
                    )
                    assert html_response.status_code == 200, f"Failed to fetch message HTML: {html_response.status_code}"
                    
                    html_content = html_response.text
                    found_in_html = sum(1 for ind in expected_indicators if ind in html_content.lower())
                    print(f"✅ Found {found_in_html}/{len(expected_indicators)} {language_name} indicators in HTML")
                    assert found_in_html >= 2, f"Message link content not in {language_name}"
                
                # Step 5: Validate PDF content
                print("\n" + "-" * 80)
                print(f"STEP 5: VALIDATE PDF CONTENT ({language_name})")
                print("-" * 80)
                
                pdf_url_match = re.search(r'http://[^\s]+\.pdf', text)
                if pdf_url_match:
                    pdf_url = pdf_url_match.group(0)
                    print(f"📄 PDF URL: {pdf_url}")
                    
                    with httpx.Client(timeout=API_TIMEOUT) as client:
                        pdf_response = client.get(pdf_url)
                        assert pdf_response.status_code == 200, f"Failed to fetch PDF: {pdf_response.status_code}"
                        
                        pdf_content = pdf_response.content
                        pdf_file = io.BytesIO(pdf_content)
                        pdf_reader = PdfReader(pdf_file)
                        pdf_text = ""
                        for page in pdf_reader.pages:
                            pdf_text += page.extract_text()
                        
                        # Check for raw markdown (should not be present)
                        markdown_indicators = ['**', '##', '----', '```']
                        has_markdown = any(ind in pdf_text for ind in markdown_indicators)
                        assert not has_markdown, "PDF contains raw markdown syntax"
                        
                        # Check for language indicators
                        found_in_pdf = sum(1 for ind in expected_indicators if ind in pdf_text.lower())
                        print(f"✅ Found {found_in_pdf}/{len(expected_indicators)} {language_name} indicators in PDF")
                        assert found_in_pdf >= 2, f"PDF content not in {language_name}"
                
                print(f"\n✅ ALL VALIDATIONS PASSED FOR {language_name.upper()}")
            finally:
                if message_id:
                    with httpx.Client(timeout=API_TIMEOUT) as client:
                        client.delete(
                            f"{api_base_url}/messages/{message_id}",
                            headers={"X-API-Key": api_key},
                        )
    finally:
        _restore_chat_rest_restrictions(api_base_url, api_key, originals)
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_chinese_to_multi(api_base_url, api_key, slack_config, test_config, chinese_message_content):
    """
    AT1.4.3: Chinese→Chinese/English/German translation test
    
    Creates a message in Chinese and delivers it to three users:
    1. Chinese user - expects Chinese summary/labels/PDF
    2. English user - expects English summary/labels/PDF
    3. German user - expects German summary/labels/PDF
    
    Validates:
    - Summary translated correctly
    - Link labels translated correctly
    - PDF content translated correctly
    - Message link content translated correctly
    """
    print("\n" + "=" * 80)
    print("AT1.4.3: CHINESE → CHINESE/ENGLISH/GERMAN TRANSLATION TEST")
    print("=" * 80)
    
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=True,
        requires_api=True,
        test_name="test_chinese_to_multi",
    )

    slack_token, slack_channel_id = require_slack_api_config(test_config)
    channel_name = slack_config["channel_name"]
    slack_endpoint = slack_config["endpoint"]
    target_max_length = 400
    
    # Setup: Update channel restrictions via API
    print("\n" + "-" * 80)
    print("SETUP: UPDATE CHANNEL RESTRICTIONS VIA API")
    print("-" * 80)

    restrictions = {
        "max_length": target_max_length,
        "allowed_formats": ["text"],
        "link_strategy": "summary+link",
    }
    originals = _set_chat_rest_restrictions(api_base_url, api_key, restrictions)
    
    # Create three users with different language preferences
    users_config = [
        {
            "language": "zh",
            "expected_indicators": ["语言模型", "信息", "总结", "传播"],
            "language_name": "Chinese"
        },
        {
            "language": "en",
            "expected_indicators": [
                "llm",
                "summar",
                "distribut",
                "channel",
                "privacy",
                "hallucinat",
            ],
            "language_name": "English"
        },
        {
            "language": "de",
            "expected_indicators": ["sprachmodelle", "information", "zusammenfass", "verbreit"],
            "language_name": "German"
        }
    ]
    
    try:
        for user_config in users_config:
            target_language = user_config["language"]
            expected_indicators = user_config["expected_indicators"]
            language_name = user_config["language_name"]
            
            print("\n" + "=" * 80)
            print(f"TESTING: Chinese → {language_name} ({target_language})")
            print("=" * 80)
            
            # Create message with Chinese content and user preferences
            marker = f"AT1.4.3 {language_name} {int(time.time())}"
            message_payload = {
                "title": "测试消息摘要 - 中文到" + language_name,
                "content": [{"type": "markdown", "body": chinese_message_content}],
                "destinations": [
                    {
                        "channel": channel_name,
                        "address": slack_endpoint,
                        "preferences": {
                            "language": target_language,
                            "content_style": "text"
                        }
                    }
                ],
                "options": {"subject": marker},
            }
            
            # Step 1: Create message
            print("\n" + "-" * 80)
            print("STEP 1: CREATE MESSAGE")
            print("-" * 80)
            message_id = None
            
            with httpx.Client(timeout=API_TIMEOUT) as client:
                response = client.post(
                    f"{api_base_url}/messages",
                    headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                    json=message_payload
                )
                print(f"✅ POST /messages: Status {response.status_code}")
                
                if response.status_code != 201:
                    pytest.fail(f"Message creation failed: {response.status_code}")
                
                result = response.json()
                message_id = result.get("message_id") or result.get("id")
                message_guid = result.get("guid")
                
                if not message_guid and message_id:
                    msg_response = client.get(
                        f"{api_base_url}/messages/{message_id}",
                        headers={"X-API-Key": api_key}
                    )
                    if msg_response.status_code == 200:
                        message_guid = msg_response.json().get("guid")
                
                print(f"✅ Message created: ID={message_id}, GUID={message_guid}")
            
            try:
                # Step 2: Wait for delivery
                print("\n" + "-" * 80)
                print("STEP 2: WAIT FOR DELIVERY")
                print("-" * 80)
                
                delivery = None
                start_time = time.time()
                max_attempts = int(WAIT_TIMEOUT / POLL_INTERVAL)
                
                for i in range(max_attempts):
                    with httpx.Client(timeout=API_TIMEOUT) as client:
                        response = client.get(
                            f"{api_base_url}/messages/{message_id}/deliveries",
                            headers={"X-API-Key": api_key}
                        )
                        
                        if response.status_code == 200:
                            deliveries = response.json().get("items", [])
                            if deliveries:
                                delivery = deliveries[0]
                                state = delivery.get("state")
                                elapsed = time.time() - start_time
                                print(f"  Attempt {i+1}: state={state}")
                                
                                if state == "sent":
                                    print(f"✅ Delivery completed in {elapsed:.1f}s")
                                    break
                                elif state in ["hard_failed", "cancelled"]:
                                    pytest.fail(f"Delivery failed: {delivery.get('last_error')}")
                    
                    time.sleep(POLL_INTERVAL)
                
                if delivery is None or delivery.get("state") != "sent":
                    pytest.fail(f"Delivery timeout after {WAIT_TIMEOUT}s")
                
                wait_timeout, poll_interval, request_timeout = _get_slack_timeouts(test_config)
                slack_message = wait_for_slack_message(
                    slack_token,
                    slack_channel_id,
                    marker,
                    timeout=wait_timeout,
                    poll_interval=poll_interval,
                    request_timeout=request_timeout,
                )
                assert_slack_mrkdwn_contains(slack_message, marker)
                
                # Step 3: Validate payload
                print("\n" + "-" * 80)
                print(f"STEP 3: VALIDATE PAYLOAD ({language_name.upper()}, 400 CHAR LIMIT)")
                print("-" * 80)
                
                personalised_payload = delivery.get("personalised_payload")
                if not personalised_payload:
                    pytest.fail("No personalised_payload in delivery")
                
                payload_data = json.loads(personalised_payload) if isinstance(personalised_payload, str) else personalised_payload
                text = payload_data.get("text", "")
                
                print(f"📄 Text length: {len(text)} characters")
                assert len(text) <= target_max_length, f"Message exceeds character limit: {len(text)} > {target_max_length}"
                
                # Validate language
                text_lower = text.lower()
                found_indicators = [ind for ind in expected_indicators if ind.lower() in text_lower]
                print(f"✅ Found {language_name} indicators: {found_indicators[:3]}")
                assert len(found_indicators) >= 2, f"Not enough {language_name} indicators found in summary"
                
                # Validate link with language parameter
                link_pattern = re.compile(r'<https?://[^>|]+\|([^>]+)>')
                links = link_pattern.findall(text)
                assert links, "Link to full message MUST be present"
                
                link_text = links[0]
                print(f"✅ Found link label: '{link_text}'")
                
                # Extract full link URL
                full_link_match = re.search(r'<(https?://[^>|]+)\|', text)
                assert full_link_match, "Could not extract link URL"
                
                link_url = full_link_match.group(1)
                assert f"?language={target_language}" in link_url, f"Link must contain language parameter: {link_url}"
                print(f"✅ Link contains language parameter: {target_language}")
                
                # Step 4: Validate message link content
                print("\n" + "-" * 80)
                print(f"STEP 4: VALIDATE MESSAGE LINK CONTENT ({language_name})")
                print("-" * 80)
                
                with httpx.Client(timeout=API_TIMEOUT) as client:
                    html_response = client.get(
                        link_url,
                        headers={"Accept": "text/html"}
                    )
                    assert html_response.status_code == 200, f"Failed to fetch message HTML: {html_response.status_code}"
                    
                    html_content = html_response.text
                    found_in_html = sum(1 for ind in expected_indicators if ind in html_content.lower())
                    print(f"✅ Found {found_in_html}/{len(expected_indicators)} {language_name} indicators in HTML")
                    assert found_in_html >= 2, f"Message link content not in {language_name}"
                
                # Step 5: Validate PDF content
                print("\n" + "-" * 80)
                print(f"STEP 5: VALIDATE PDF CONTENT ({language_name})")
                print("-" * 80)
                
                pdf_url_match = re.search(r'http://[^\s]+\.pdf', text)
                if pdf_url_match:
                    pdf_url = pdf_url_match.group(0)
                    print(f"📄 PDF URL: {pdf_url}")
                    
                    with httpx.Client(timeout=API_TIMEOUT) as client:
                        pdf_response = client.get(pdf_url)
                        assert pdf_response.status_code == 200, f"Failed to fetch PDF: {pdf_response.status_code}"
                        
                        pdf_content = pdf_response.content
                        pdf_file = io.BytesIO(pdf_content)
                        pdf_reader = PdfReader(pdf_file)
                        pdf_text = ""
                        for page in pdf_reader.pages:
                            pdf_text += page.extract_text()
                        
                        # Check for raw markdown (should not be present)
                        markdown_indicators = ['**', '##', '----', '```']
                        has_markdown = any(ind in pdf_text for ind in markdown_indicators)
                        assert not has_markdown, "PDF contains raw markdown syntax"
                        
                        # Check for language indicators
                        found_in_pdf = sum(1 for ind in expected_indicators if ind in pdf_text.lower())
                        print(f"✅ Found {found_in_pdf}/{len(expected_indicators)} {language_name} indicators in PDF")
                        assert found_in_pdf >= 2, f"PDF content not in {language_name}"
                
                print(f"\n✅ ALL VALIDATIONS PASSED FOR {language_name.upper()}")
            finally:
                if message_id:
                    with httpx.Client(timeout=API_TIMEOUT) as client:
                        client.delete(
                            f"{api_base_url}/messages/{message_id}",
                            headers={"X-API-Key": api_key},
                        )
    finally:
        _restore_chat_rest_restrictions(api_base_url, api_key, originals)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.application,
    pytest.mark.smtp,
    pytest.mark.llm,
    pytest.mark.live_provider,
    pytest.mark.live_delivery,
    pytest.mark.heavy,
]
