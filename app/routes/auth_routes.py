# app/routes/auth_routes.py
from flask import Blueprint, request, jsonify
from app.controllers.auth_controller import AuthController
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError
from app.models.a1c import A1cRecord
import traceback

auth_bp = Blueprint("auth", __name__) 

@auth_bp.post("/register")            
def register():
    print("Register endpoint called")  # 調試輸出
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    account = data.get("account") or None  
    result, status = AuthController.register(email, password, account)
    return jsonify(result), status


@auth_bp.get("/register/check")
def check_register():
    try:
        email = request.args.get("email")
        
        if not email:
            return jsonify({
                "status": "1",
                "message": "email 參數不能為空"
            }), 400
        result, status = AuthController.check_email(email)
        return jsonify(result), status
        
    except Exception as e:
        import traceback
        return jsonify({
            "status": "1",
            "message": "檢查失敗"
        }), 500


@auth_bp.post("/auth")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    result, status = AuthController.login(email, password)
    
    return jsonify(result), status  # 簡化處理


@auth_bp.post("/verification/send")
def send_verification():
    data = request.get_json()
    print("1",data)  # 調試輸出
    email = data.get("email")
    
    result, status = AuthController.send_verification(email)  # 使用正確的方法名
    print("2",result)  # 調試輸出
    return jsonify(result), status


@auth_bp.post("/verification/check")
def verify_code():
    try:
        data = request.get_json()
        email = data.get("email")
        code = data.get("code")
        result, status = AuthController.verify_code(email, code)  # 使用正確的方法名
        print("1",result)

        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "驗證失敗"
        }), 500


@auth_bp.post("/password/forgot")
def forgot_password():
    email = request.json.get("email")
    result, status = AuthController.forgot_password(email)
    return jsonify(result), status



@auth_bp.post("/password/reset")
@jwt_required()
def reset_password():
    email = get_jwt_identity()  
    if not isinstance(email, str):
        return jsonify({
            "status": "1",
            "message": "無效的使用者識別"
        }), 422
        
    new_password = request.json.get("password")
    result, status = AuthController.reset_password(email, new_password)
    return jsonify(result), status


@auth_bp.get("/user")
@jwt_required()
def get_user():
    print("Get user endpoint called")
    try:
        email = get_jwt_identity()
        
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": f"無效的使用者識別類型: {type(email).__name__}"
            }), 422
        
        result, status = AuthController.get_user(email)
        return jsonify(result), status
        
    except Exception as e:
        print(traceback.format_exc())  # 修正：移除參數
        return jsonify({
            "status": "1",
            "message": "身份驗證失敗"
        }), 500


@auth_bp.patch("/user")
@jwt_required()
def update_user():
    print("Update user endpoint called")
    try:
        email = get_jwt_identity()
        
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        user_data = request.get_json(silent=True) or {}
            
        result, status = AuthController.update_user(email, user_data)
        return jsonify(result), status
        
    except Exception as e:
        print(traceback.format_exc())  # 修正：移除參數
        return jsonify({
            "status": "1",
            "message": f"更新失敗: {str(e)}"
        }), 500
    

@auth_bp.patch("/user/setting")
@jwt_required()
def update_user_setting():
    print("Update user setting endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        
        # 確保 email 是字串
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        # 取得請求資料
        setting_data = request.get_json(silent=True) or {}
        
        print(f"Update user setting request - Email: {email}, Data: {setting_data}")
        
        result, status = AuthController.update_user_setting(email, setting_data)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": f"更新設定失敗: {str(e)}"
        }), 500
    

@auth_bp.post("/user/weight")
@jwt_required()
def add_weight():
    print("Add weight endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()

        # 確保 email 是字串
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        weight = request.json.get("weight")
        date = request.json.get("date")  # 可選參數
        
        result, status = AuthController.add_weight(email, weight, date)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": f"新增體重失敗: {str(e)}"
        }), 500
    

@auth_bp.get("/user/medical")
@jwt_required()
def get_medical_records():
    print("Get medical records endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        result, status = AuthController.get_medical_records(email)
        return jsonify(result), status
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "取得病歷失敗"
        }), 500


@auth_bp.patch("/user/medical")
@jwt_required()
def update_medical_records():
    print("Update medical records endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        
        # 確保 email 是字串
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        # 取得請求資料
        medical_data = request.get_json(silent=True) or {}
        
        result, status = AuthController.update_medical_records(email, medical_data)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "更新病歷失敗"
        }), 500
    

@auth_bp.post("/user/a1c")
@jwt_required()
def add_a1c(): 
    print("Add A1C endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        
        # 確保 email 是字串
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        a1c = request.json.get("a1c")
        date = request.json.get("date")  # 可選參數
        
        result, status = AuthController.add_a1c(email, a1c, date)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": f"新增 A1C 失敗: {str(e)}"
        }), 500
    



@auth_bp.get("/user/a1c")
@jwt_required()
def get_a1c_records():
    print("Get A1C records endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        result, status = AuthController.get_a1c_records(email)
        return jsonify(result), status
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "取得 A1C 紀錄失敗"
        }), 500
    


@auth_bp.post("/user/care")
@jwt_required() 
def add_care_record():
    print("Add care record endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        care_data = request.json.get("care_data")
        result, status = AuthController.add_care_record(email, care_data)
        return jsonify(result), status

    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "新增照護紀錄失敗"
        }), 500
    

@auth_bp.get("/user/care")
@jwt_required()
def get_care_records():
    print("Get care records endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        result, status = AuthController.get_care_records(email)
        return jsonify(result), status
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "取得照護紀錄失敗"
        }), 500


@auth_bp.post("/share")
@jwt_required()
def add_share():
    print("Add share endpoint called")
    try:
        email = get_jwt_identity()
        
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        data = request.get_json(silent=True) or {}
        
        record_type = data.get('type')
        record_id = data.get('id')
        relation_type = data.get('relation_type')
        
        # 驗證必要參數
        if record_type is None or record_id is None or relation_type is None:
            return jsonify({
                "status": "1",
                "message": "缺少必要參數"
            }), 400
            
        # 型態驗證
        try:
            record_type = int(record_type)
            record_id = int(record_id)
            relation_type = int(relation_type)
        except (ValueError, TypeError):
            return jsonify({
                "status": "1",
                "message": "參數型態錯誤"
            }), 400
        
        result, status = AuthController.add_share_record(email, record_type, record_id, relation_type)
        return jsonify(result), status
        
    except Exception as e:
        print(f"Add share route error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "status": "1",
            "message": "分享失敗"
        }), 500

@auth_bp.get("/share/<relation_type>")
@jwt_required()
def get_shared_records(relation_type):
    print("Get shared records endpoint called")
    try:
        email = get_jwt_identity()
        
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        result, status = AuthController.get_shared_records(email, relation_type)
        return jsonify(result), status
        
    except Exception as e:
        print(f"Get shared records route error: {str(e)}")
        print(traceback.format_exc())  # 修正：移除參數 e
        return jsonify({
            "status": "1",
            "message": "取得分享記錄失敗"
        }), 500


@auth_bp.get("/news")
@jwt_required()
def get_news():
    print("Get news endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        
        # 確保 email 是字串
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        result, status = AuthController.get_news(email)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "取得最新消息失敗"
        }), 500


@auth_bp.get("/friend/list")
@jwt_required()
def get_friend_list():
    print("Get friend list endpoint called")
    try:
        email = get_jwt_identity()

        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422

        result, status = AuthController.get_friend_list(email)
        return jsonify(result), status

    except Exception as e:
        print(f"Get friend list route error: {str(e)}")
        print(traceback.format_exc())  # 修正：移除參數
        return jsonify({
            "status": "1",
            "message": "取得好友列表失敗"
        }), 500

@auth_bp.post("/friend")
@jwt_required()
def add_friend():
    print("Add friend endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        data = request.get_json(silent=True) or {}
        friend_name = data.get('name')
        relation_type = data.get('relation_type', 0)
        
        result, status = AuthController.add_friend(email, friend_name, relation_type)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "新增好友失敗"
        }), 500
    


@auth_bp.get("/user/diary")
@jwt_required()
def get_diary_entries():
    print("Get diary entries endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        
        # 確保 email 是字串
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        # 從查詢參數獲取日期
        date = request.args.get('date')  # 可選參數
        
        result, status = AuthController.get_diary_entries(email, date)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "取得日記失敗"
        }), 500

@auth_bp.put("/user/badge")
@jwt_required()
def update_user_badge():
    print("Update badge endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        
        # 確保 email 是字串
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        # 取得請求資料
        data = request.get_json(silent=True) or {}
        
        # 嘗試兩種可能的參數名稱
        badge = data.get('Badge') or data.get('badge')
        
        # 驗證必要參數
        if badge is None:
            return jsonify({
                "status": "1",
                "message": "缺少 Badge 參數"
            }), 400
        
        result, status = AuthController.update_user_badge(email, badge)
        return jsonify(result), status
        
    except Exception as e:
        print(f"Request data: {request.get_json(silent=True)}")
        return jsonify({
            "status": "1",
            "message": "更新徽章失敗"
        }), 500
    


@auth_bp.post("/user/records")
@jwt_required()
def get_user_records():
    print("Get user records endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        
        # 確保 email 是字串
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        # 取得請求資料
        data = request.get_json(silent=True) or {}
        diet = data.get('diet')  # 時段參數
        
        result, status = AuthController.get_user_records(email, diet)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "取得健康記錄失敗"
        }), 500
    

@auth_bp.delete("/user/records")
@jwt_required()
def delete_user_records():
    print("Delete user records endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422

        # 取得請求資料
        data = request.get_json(silent=True) or {}
        delete_ids = data.get('deleteObject', [])

        # 驗證 deleteObject 必須是 list
        # if not isinstance(delete_ids, list):
        #     print(delete_ids, type(delete_ids))  # 調試輸出
        #     return jsonify({
        #         "status": "1",
        #         "message": "deleteObject 必須為陣列"
        #     }), 400

        # 呼叫 controller 處理
        result, status = AuthController.delete_user_records(email, delete_ids)
        return jsonify(result), status

    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "刪除健康記錄失敗"
        }), 500
    


@auth_bp.post("/user/blood/sugar")
@jwt_required()
def add_blood_sugar():
    print("Add blood sugar endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        print(f"Processing blood sugar for user: {email}")
        
        # 確保 email 是字串
        if not isinstance(email, str):
            print("Invalid email format")
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        # 取得請求資料
        data = request.get_json(silent=True) or {}
        print(f"Received data: {data}")
        
        timeperiod = data.get('timeperiod')
        recorded_at = data.get('recorded_at')
        drug = data.get('drug')
        exercise = data.get('exercise')

        
        print("Calling AuthController.add_blood_sugar...")
        result, status = AuthController.add_blood_sugar(
            email=email,
            sugar=data.get('sugar'),
            timeperiod=timeperiod,
            recorded_at=recorded_at,
            drug=drug,
            exercise=exercise
        )
        
        print(f"Controller returned: {result}, status: {status}")
        response = jsonify(result)
        print(f"Final response: {response.get_json()}")
        return response, status
        
    except Exception as e:
        import traceback
        traceback.print_exc()  # 打印完整堆疊追蹤
        return jsonify({
            "status": "1",
            "message": "新增血糖記錄失敗"
        }), 500




@auth_bp.get("/friend/code")
@jwt_required()
def get_friend_invite_code():
    print("Get friend invite code endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422

        result, status = AuthController.get_friend_invite_code(email)
        return jsonify(result), status

    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "取得邀請碼失敗"
        }), 500

@auth_bp.get("/friend/results")
@jwt_required()
def get_friend_results():
    print("Get friend results endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422

        result, status = AuthController.get_friend_results(email)
        return jsonify(result), status

    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "取得邀請結果失敗"
        }), 500

@auth_bp.get("/friend/requests")
@jwt_required()
def get_friend_requests():
    print("Get friend requests endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422

        result, status = AuthController.get_friend_requests(email)
        return jsonify(result), status

    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "取得邀請列表失敗"
        }), 500
    






@auth_bp.post("/user/diet")
@jwt_required()
def add_diet_record():
    print("Add diet record endpoint called")
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422

        data = request.get_json(silent=True) or {}
        description = data.get("description", "")
        meal = data.get("meal", 0)
        tag = data.get("tag", [])  # List[String]
        image = data.get("image", 0)
        lat = data.get("lat", None)
        lng = data.get("lng", None)
        recorded_at = data.get("recorded_at", None)

        result, status = AuthController.add_diet_record(
            email=email,
            description=description,
            meal=meal,
            tag=tag,
            image=image,
            lat=lat,
            lng=lng,
            recorded_at=recorded_at
        )
        return jsonify(result), status

    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "新增飲食記錄失敗"
        }), 500
    


@auth_bp.post("/user/blood/pressure")
@jwt_required()
def add_blood_pressure():
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422

        data = request.get_json(silent=True) or {}
        systolic = data.get("Systolic") or data.get("systolic")
        diastolic = data.get("Diastolic") or data.get("diastolic")
        pulse = data.get("Pulse") or data.get("pulse")
        recorded_at = data.get("Recorded_at") or data.get("recorded_at")

        # 檢查必填參數
        if systolic is None or diastolic is None or pulse is None:
            return jsonify({
                "status": "1",
                "message": "血壓與心跳參數不能為空"
            }), 400

        result, status = AuthController.add_blood_pressure(
            email=email,
            systolic=systolic,
            diastolic=diastolic,
            pulse=pulse,
            recorded_at=recorded_at
        )
        return jsonify(result), status

    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "新增血壓記錄失敗"
        }), 500
    


@auth_bp.post("/friend/send")
@jwt_required()
def send_friend_invite():
    print("Send friend invite endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "無效的使用者識別"
            }), 422
        
        data = request.get_json(silent=True) or {}
        invite_code = data.get("invite_code")
        relation_type = data.get("type")  # 0: 醫師團; 1: 親友團; 2: 糖友團
        
        # 驗證必要參數
        if invite_code is None or relation_type is None:
            return jsonify({
                "status": "1",
                "message": "缺少必要參數"
            }), 400
        
        # 型態驗證
        try:
            relation_type = int(relation_type)
        except (ValueError, TypeError):
            return jsonify({
                "status": "1",
                "message": "參數型態錯誤"
            }), 400
        
        # 呼叫控制器處理邀請碼邏輯
        result, status = AuthController.send_friend_invite(email, invite_code, relation_type)
        return jsonify(result), status
        
    except Exception as e:
        print(f"Send friend invite route error: {str(e)}")
        return jsonify({
            "status": "1",
            "message": "發送邀請失敗"
        }), 500