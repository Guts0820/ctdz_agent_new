"""
验证任务六：批次管理功能测试

测试流程：
1. 创建批次，包含3道题，默认状态locked
2. 提交错误作答，确认final_answer_explanation为空
3. 一键放行后，重新提交，确认能看到完整答案
4. 创建另一个批次，精细放行只放1道题
5. 验证不属于任何批次的旧题目不受影响
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def print_section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)

def test_create_batch():
    """测试1：创建批次"""
    print_section("测试1：创建作业批次（3道题，默认locked）")
    
    payload = {
        "class_id": "C-001",
        "teacher_id": "T-001",
        "batch_date": "2026-08-04",
        "question_ids": ["Q-0001", "Q-0002", "Q-0003"]
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/teacher/homework_batch", json=payload, timeout=10)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        return resp.json().get("batch_id")
    except Exception as e:
        print(f"❌ 创建批次失败: {e}")
        return None

def test_submit_locked_question(question_id, student_id="S-0001"):
    """测试2：提交locked状态题目的错误作答"""
    print_section(f"测试2：提交locked题目 {question_id} 的错误作答")
    
    payload = {
        "student_id": student_id,
        "question_id": question_id,
        "original_question": "小明有25颗糖果，小红有38颗糖果，他们一共有多少颗糖果？",
        "student_write": "53"  # 错误答案
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/submit", json=payload, timeout=30)
        print(f"状态码: {resp.status_code}")
        data = resp.json()
        print(f"judge_result: {data.get('data', {}).get('judge_result')}")
        print(f"answer_released: {data.get('data', {}).get('answer_released')}")
        
        final_answer = data.get('data', {}).get('final_answer_explanation')
        explanation = data.get('data', {}).get('explanation', '')
        
        print(f"\nfinal_answer_explanation: {final_answer if final_answer else '(空)'}")
        print(f"\nexplanation (前100字): {explanation[:100]}...")
        
        if final_answer is None:
            print("✅ 验证通过：final_answer_explanation为空")
        else:
            print("❌ 验证失败：final_answer_explanation不为空")
        
        return data
    except Exception as e:
        print(f"❌ 提交失败: {e}")
        return None

def test_release_batch(batch_id):
    """测试3：一键放行批次"""
    print_section(f"测试3：一键放行批次 {batch_id}")
    
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/teacher/homework_batch/{batch_id}/release", timeout=10)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        return resp.json().get("status") == "success"
    except Exception as e:
        print(f"❌ 放行失败: {e}")
        return False

def test_submit_released_question(question_id, student_id="S-0001"):
    """测试4：提交已放行题目的错误作答"""
    print_section(f"测试4：提交已放行题目 {question_id} 的错误作答")
    
    payload = {
        "student_id": student_id,
        "question_id": question_id,
        "original_question": "小明有25颗糖果，小红有38颗糖果，他们一共有多少颗糖果？",
        "student_write": "53"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/submit", json=payload, timeout=30)
        print(f"状态码: {resp.status_code}")
        data = resp.json()
        print(f"judge_result: {data.get('data', {}).get('judge_result')}")
        print(f"answer_released: {data.get('data', {}).get('answer_released')}")
        
        final_answer = data.get('data', {}).get('final_answer_explanation')
        print(f"\nfinal_answer_explanation (前150字): {final_answer[:150] if final_answer else '(空)'}...")
        
        if final_answer:
            print("✅ 验证通过：能看到完整答案讲解")
        else:
            print("❌ 验证失败：final_answer_explanation仍为空")
        
        return data
    except Exception as e:
        print(f"❌ 提交失败: {e}")
        return None

def test_create_batch2():
    """测试5：创建第二个批次"""
    print_section("测试5：创建第二个批次（用于精细放行测试）")
    
    payload = {
        "class_id": "C-002",
        "teacher_id": "T-001",
        "batch_date": "2026-08-05",
        "question_ids": ["Q-0004", "Q-0005", "Q-0001"]
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/teacher/homework_batch", json=payload, timeout=10)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        return resp.json().get("batch_id")
    except Exception as e:
        print(f"❌ 创建批次失败: {e}")
        return None

def test_release_partial(batch_id, question_ids):
    """测试6：精细放行部分题目"""
    print_section(f"测试6：精细放行批次 {batch_id} 的部分题目")
    
    payload = {"question_ids": question_ids}
    
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/teacher/homework_batch/{batch_id}/release_partial",
            json=payload,
            timeout=10
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
        return resp.json().get("status") == "success"
    except Exception as e:
        print(f"❌ 精细放行失败: {e}")
        return False

def test_old_question():
    """测试7：验证不属于任何批次的旧题目"""
    print_section("测试7：验证旧题目（不属于任何批次）")
    
    # Q-0001已经属于批次，用Q-0005来测试（如果不在第二个批次中）
    # 或者使用一个不存在的question_id
    payload = {
        "student_id": "S-0001",
        "question_id": "Q-OLD-001",  # 不存在的题目ID
        "original_question": "测试题目",
        "student_write": "错误答案"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/submit", json=payload, timeout=30)
        print(f"状态码: {resp.status_code}")
        data = resp.json()
        
        # 由于题目不存在，可能会返回错误，这里主要验证answer_released字段
        answer_released = data.get('data', {}).get('answer_released')
        print(f"answer_released: {answer_released}")
        
        if answer_released == True:
            print("✅ 验证通过：不属于任何批次的题目，answer_released为True")
        else:
            print(f"❌ 验证失败：answer_released为{answer_released}")
        
        return data
    except Exception as e:
        print(f"⚠️  旧题目测试异常（预期可能出错）: {e}")
        return None

def main():
    print("=" * 60)
    print("  批次管理功能验证测试")
    print("=" * 60)
    
    # 测试1：创建批次
    batch_id_1 = test_create_batch()
    if not batch_id_1:
        print("\n❌ 无法继续测试，请检查服务是否启动")
        return
    
    # 测试2：提交locked题目
    test_submit_locked_question("Q-0001")
    
    # 测试3：一键放行
    if test_release_batch(batch_id_1):
        # 测试4：提交已放行题目
        test_submit_released_question("Q-0001")
    
    # 测试5：创建第二个批次
    batch_id_2 = test_create_batch2()
    
    # 测试6：精细放行（只放行Q-0004）
    if batch_id_2 and test_release_partial(batch_id_2, ["Q-0004"]):
        print_section("测试6.1：精细放行后，提交已放行的题目Q-0004")
        test_submit_released_question("Q-0004")
        
        print_section("测试6.2：精细放行后，提交未放行的题目Q-0005")
        test_submit_locked_question("Q-0005")
    
    # 测试7：旧题目验证
    test_old_question()
    
    print_section("验证完成")

if __name__ == "__main__":
    main()