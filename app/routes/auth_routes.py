# app/routes/auth_routes.py
from flask import Blueprint, request, jsonify
from app.controllers.auth_controller import AuthController
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError
from app.models.a1c import A1cRecord
from app.utils.api_response import APIResponse, missing_auth, invalid_auth, auth_failed, invalid_user_id
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
            return APIResponse.validation_error(
                "Email parameter cannot be empty", 
                "EMAIL_REQUIRED"
            )
        
        result, status = AuthController.check_email(email)
        return jsonify(result), status
        
    except Exception as e:
        return APIResponse.handle_exception(e, "Check failed", "CHECK_FAILED")


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
        return APIResponse.handle_exception(e, "Verification failed", "VERIFICATION_FAILED")


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
            "message": "Invalid user identification",
            "message_code": "INVALID_USER_ID"
        }), 422
        
    new_password = request.json.get("password")
    result, status = AuthController.reset_password(email, new_password)
    return jsonify(result), status


@auth_bp.get("/user")
def get_user():
    print("Get user endpoint called")
    
    # 路由級別記憶體監控
    try:
        import psutil
        import os
        import gc
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024
        print(f"[ROUTE] user start: {memory_before:.2f} MB")
    except:
        pass
    
    try:
        # 安全的 JWT 驗證
        try:
            from flask_jwt_extended import verify_jwt_in_request
            verify_jwt_in_request()
            email = get_jwt_identity()
        except NoAuthorizationError:
            print("No authorization header found")
            return missing_auth()
        except InvalidHeaderError as e:
            print(f"Invalid JWT header: {e}")
            return invalid_auth()
        except Exception as jwt_error:
            print(f"JWT validation error: {jwt_error}")
            return auth_failed()
        
        if not isinstance(email, str) or not email.strip():
            print(f"Invalid email format: {email} (type: {type(email)})")
            return invalid_user_id()
        
        result, status = AuthController.get_user(email)
        
        # 路由結束前強制清理
        try:
            gc.collect()
            memory_after = process.memory_info().rss / 1024 / 1024
            print(f"[ROUTE] user end: {memory_after:.2f} MB, change: {memory_after-memory_before:+.2f} MB")
        except:
            pass
            
        return jsonify(result), status
        
    except Exception as e:
        print(f"Get user route error: {e}")
        print(traceback.format_exc())
        return jsonify({
            "status": "1",
            "message": "System error",
            "message_code": "SYSTEM_ERROR"
        }), 500
    finally:
        # 路由級別強制清理
        try:
            import gc
            # 確保資料庫連接正常關閉
            try:
                from app.extensions import db
                db.session.remove()
            except Exception as db_cleanup_error:
                print(f"[ROUTE] DB cleanup error in user: {db_cleanup_error}")
            
            collected = gc.collect()
            print(f"[ROUTE] user cleanup: {collected} objects")
        except Exception as route_cleanup_error:
            print(f"[ROUTE] Cleanup error in user: {route_cleanup_error}")


@auth_bp.patch("/user")
@jwt_required()
def update_user():
    print("Update user endpoint called")
    try:
        email = get_jwt_identity()
        
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422
        
        user_data = request.get_json(silent=True) or {}
            
        result, status = AuthController.update_user(email, user_data)
        return jsonify(result), status
        
    except Exception as e:
        print(traceback.format_exc())  # 修正：移除參數
        return jsonify({
            "status": "1",
            "message": f"Update failed: {str(e)}",
            "message_code": "UPDATE_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422

        weight = request.json.get("weight")
        result, status = AuthController.add_weight(email, weight, recorded_at=request.json.get("recorded_at"))
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
            "message": "Failed to get medical records",
                "message_code": "GET_MEDICAL_RECORDS_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422
        
        # 取得請求資料
        medical_data = request.get_json(silent=True) or {}
        
        result, status = AuthController.update_medical_records(email, medical_data)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "Failed to update medical records",
                "message_code": "UPDATE_MEDICAL_RECORDS_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
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
            "message": "Failed to get A1C records",
                "message_code": "GET_A1C_FAILED"
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
            "message": "Failed to add care record",
                "message_code": "ADD_CARE_FAILED"
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
            "message": "Failed to get care records",
                "message_code": "GET_CARE_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422
        
        data = request.get_json(silent=True) or {}
        print(f"Received share data: {data}")  # 調試用

        record_type = data.get('type')
        record_id = data.get('id')
        relation_type = data.get('relation_type')
        
        # 詳細的參數檢查
        missing_params = []
        if record_type is None:
            missing_params.append('type')
        if record_id is None:
            missing_params.append('id')
        if relation_type is None:
            missing_params.append('relation_type')
            
        if missing_params:
            return jsonify({
                "status": "1",
                "message": f"缺少必要參數: {', '.join(missing_params)}"
            }), 400
            
        # 型態驗證
        try:
            record_type = int(record_type)
            record_id = int(record_id)
            relation_type = int(relation_type)
        except (ValueError, TypeError) as e:
            return jsonify({
                "status": "1",
                "message": f"Parameter type error: {str(e)}",
                "message_code": "PARAMETER_TYPE_ERROR"
            }), 400
        
        # 驗證 relation_type 範圍
        if relation_type not in [0, 1, 2]:
            return jsonify({
                "status": "1",
                "message": "relation_type must be 0(doctor), 1(family), or 2(friend)",
                "message_code": "INVALID_RELATION_TYPE"
            }), 400
        
        result, status = AuthController.add_share_record(email, record_type, record_id, relation_type )
        return jsonify(result), status
        
    except Exception as e:
        print(f"Add share route error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "status": "1",
            "message": "Share failed",
                "message_code": "SHARE_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422
        
        result, status = AuthController.get_shared_records(email, relation_type)
        return jsonify(result), status
        
    except Exception as e:
        print(f"Get shared records route error: {str(e)}")
        print(traceback.format_exc())  # 修正：移除參數 e
        return jsonify({
            "status": "1",
            "message": "Failed to get shared records",
            "message_code": "GET_SHARED_RECORDS_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422
        
        result, status = AuthController.get_news(email)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "Failed to get news",
            "message_code": "GET_NEWS_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422

        result, status = AuthController.get_friend_list(email)
        return jsonify(result), status

    except Exception as e:
        print(f"Get friend list route error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "status": "1",
            "message": "Failed to get friends list",
            "message_code": "GET_FRIENDS_LIST_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422
        
        data = request.get_json(silent=True) or {}
        friend_name = data.get('name')
        relation_type = data.get('relation_type', 0)
        
        result, status = AuthController.add_friend(email, friend_name, relation_type)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "Failed to add friend",
                "message_code": "ADD_FRIEND_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422
        
        # 從查詢參數獲取日期
        date = request.args.get('date')  # 可選參數
        
        result, status = AuthController.get_diary_entries(email, date)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "Failed to get diary entries",
                "message_code": "GET_DIARY_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422
        
        # 取得請求資料
        data = request.get_json(silent=True) or {}
        
        # 嘗試兩種可能的參數名稱
        badge = data.get('Badge') or data.get('badge')
        
        # 驗證必要參數
        if badge is None:
            return jsonify({
                "status": "1",
                "message": "Missing badge parameter",
                "message_code": "MISSING_BADGE_PARAMETER"
            }), 400
        
        result, status = AuthController.update_user_badge(email, badge)
        return jsonify(result), status
        
    except Exception as e:
        print(f"Request data: {request.get_json(silent=True)}")
        return jsonify({
            "status": "1",
            "message": "Failed to update badge",
                "message_code": "UPDATE_BADGE_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422
        
        # 取得請求資料
        data = request.get_json(silent=True) or {}
        diet = data.get('diet')  # 時段參數
        
        result, status = AuthController.get_user_records(email, diet)
        return jsonify(result), status
        
    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "Failed to get health records",
                "message_code": "GET_HEALTH_RECORDS_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422

        # 取得請求資料
        data = request.get_json(silent=True) or {}
        delete_ids = data.get('deleteObject', [])

        # 驗證 deleteObject 必須是 list
        # if not isinstance(delete_ids, list):
        #     print(delete_ids, type(delete_ids))  # 調試輸出
        #     return jsonify({
        #         "status": "1",
        #         "message": "deleteObject must be an array",
        #         "message_code": "DELETE_OBJECT_MUST_BE_ARRAY"
        #     }), 400

        # 呼叫 controller 處理
        result, status = AuthController.delete_user_records(email, delete_ids)
        return jsonify(result), status

    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "Failed to delete health records",
                "message_code": "DELETE_HEALTH_RECORDS_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
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
            "message": "Failed to add blood sugar record",
                "message_code": "ADD_BLOOD_SUGAR_FAILED"
        }), 500




@auth_bp.get("/friend/code")
@jwt_required()
def get_friend_invite_code():
    print("Get friend invite code endpoint called")
    
    # 路由級別記憶體監控
    try:
        import psutil
        import os
        import gc
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024
        print(f"[ROUTE] friend/code start: {memory_before:.2f} MB")
    except:
        pass
    
    try:
        # 使用標準的 JWT 驗證
        email = get_jwt_identity()
        
        if not isinstance(email, str) or not email.strip():
            print(f"Invalid email format: {email} (type: {type(email)})")
            return jsonify({
                "status": "1",
                "message": "invalid user identity",
                "message_code": "INVALID_USER_IDENTITY"
            }), 422

        result, status = AuthController.get_friend_invite_code(email)
        
        # 路由結束前強制清理
        try:
            gc.collect()
            memory_after = process.memory_info().rss / 1024 / 1024
            print(f"[ROUTE] friend/code end: {memory_after:.2f} MB, change: {memory_after-memory_before:+.2f} MB")
        except:
            pass
            
        return jsonify(result), status

    except Exception as e:
        print(f"Friend code route error: {e}")
        print(traceback.format_exc())
        return jsonify({
            "status": "1",
            "message": "failed to get invite code",
            "message_code": "GET_INVITE_CODE_FAILED"
        }), 500
    finally:
        # 路由級別強制清理
        try:
            import gc
            # 確保資料庫連接正常關閉
            try:
                from app.extensions import db
                db.session.remove()
            except Exception as db_cleanup_error:
                print(f"[ROUTE] DB cleanup error in friend/code: {db_cleanup_error}")
            
            collected = gc.collect()
            print(f"[ROUTE] friend/code cleanup: {collected} objects")
        except Exception as route_cleanup_error:
            print(f"[ROUTE] Cleanup error in friend/code: {route_cleanup_error}")


@auth_bp.get("/friend/results")
@jwt_required()
def get_friend_results():
    print("Get friend results endpoint called")
    
    # 路由級別記憶體監控
    try:
        import psutil
        import os
        import gc
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024
        print(f"[ROUTE] friend/results start: {memory_before:.2f} MB")
    except:
        pass
    
    try:
        # 使用標準的 JWT 驗證
        email = get_jwt_identity()
        
        if not isinstance(email, str) or not email.strip():
            print(f"Invalid email format: {email} (type: {type(email)})")
            return jsonify({
                "status": "1",
                "message": "invalid user identity",
                "message_code": "INVALID_USER_IDENTITY"
            }), 422

        result, status = AuthController.get_friend_results(email)
        
        # 路由結束前強制清理
        try:
            gc.collect()
            memory_after = process.memory_info().rss / 1024 / 1024
            print(f"[ROUTE] friend/results end: {memory_after:.2f} MB, change: {memory_after-memory_before:+.2f} MB")
        except:
            pass
            
        return jsonify(result), status

    except Exception as e:
        print(f"Friend results route error: {e}")
        print(traceback.format_exc())
        return jsonify({
            "status": "1",
            "message": "failed to get invitation results",
            "message_code": "GET_INVITE_RESULTS_FAILED"
        }), 500
    finally:
        # 路由級別強制清理
        try:
            import gc
            # 確保資料庫連接正常關閉
            try:
                from app.extensions import db
                db.session.remove()
            except Exception as db_cleanup_error:
                print(f"[ROUTE] DB cleanup error in friend/results: {db_cleanup_error}")
            
            collected = gc.collect()
            print(f"[ROUTE] friend/results cleanup: {collected} objects")
        except Exception as route_cleanup_error:
            print(f"[ROUTE] Cleanup error in friend/results: {route_cleanup_error}")






@auth_bp.get("/friend/requests")
@jwt_required()
def get_friend_requests():
    print("Get friend requests endpoint called")  # 調試輸出
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422

        result, status = AuthController.get_friend_requests(email)
        return jsonify(result), status

    except Exception as e:
        return jsonify({
            "status": "1",
            "message": "Failed to get invitation list",
                "message_code": "GET_INVITATIONS_FAILED"
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
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
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
            "message": "Failed to add diet record",
                "message_code": "ADD_DIET_FAILED"
        }), 500
    


@auth_bp.post("/user/blood/pressure")
@jwt_required()
def add_blood_pressure():
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
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
                "message": "Blood pressure and heart rate parameters cannot be empty",
                "message_code": "BP_HR_PARAMETERS_REQUIRED"
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
            "message": "Failed to add blood pressure record",
                "message_code": "ADD_BLOOD_PRESSURE_FAILED"
        }), 500
    


@auth_bp.post("/friend/send")
@jwt_required()
def send_friend_invite():
    print("DEBUG: Friend send endpoint called")
    try:
        email = get_jwt_identity()
        print(f"DEBUG: JWT identity: {email}")
        
        if not isinstance(email, str):
            print(f"DEBUG: Invalid email type: {type(email)}")
            return jsonify({
                "status": "1",
                "message": "invalid user identity",
                "message_code": "INVALID_USER_IDENTITY"
            }), 422
        
        data = request.get_json(silent=True) or {}
        print(f"DEBUG: Received request data: {data}")
        
        invite_code = data.get("invite_code")
        relation_type = data.get("type")  # 0: 醫師團; 1: 親友團; 2: 糖友團
        
        print(f"DEBUG: invite_code={invite_code}, relation_type={relation_type}")
        
        # 驗證必要參數
        if invite_code is None or relation_type is None:
            print(f"DEBUG: Missing parameters - invite_code: {invite_code}, relation_type: {relation_type}")
            return jsonify({
                "status": "1",
                "message": "missing required parameters",
                "message_code": "MISSING_PARAMETERS"
            }), 400
        
        # 型態驗證
        try:
            relation_type = int(relation_type)
            print(f"DEBUG: Converted relation_type to int: {relation_type}")
        except (ValueError, TypeError) as e:
            print(f"DEBUG: Type conversion error: {e}")
            return jsonify({
                "status": "1",
                "message": "parameter type error",
                "message_code": "PARAMETER_TYPE_ERROR"
            }), 400
        
        print(f"DEBUG: About to call AuthController.send_friend_invite")
        # 呼叫控制器處理邀請碼邏輯
        result, status = AuthController.send_friend_invite(email, invite_code, relation_type)
        print(f"DEBUG: Controller returned - result: {result}, status: {status}")
        
        return jsonify(result), status
        
    except Exception as e:
        print(f"DEBUG: Route exception: {str(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        return jsonify({
            "status": "1",
            "message": "failed to send invitation",
            "message_code": "SEND_INVITATION_FAILED"
        }), 500

@auth_bp.get("/friend/<int:invite_id>/accept")
@jwt_required()
def accept_friend_invite(invite_id):
    print("Accept friend invite endpoint called")
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422

        result, status = AuthController.accept_friend_invite(email, invite_id)
        return jsonify(result), status

    except Exception as e:
        print(f"Accept friend invite route error: {str(e)}")
        return jsonify({
            "status": "1",
            "message": "Failed to accept invitation",
                "message_code": "ACCEPT_INVITATION_FAILED"
        }), 500

@auth_bp.get("/friend/<int:invite_id>/refuse")
@jwt_required()
def refuse_friend_invite(invite_id):
    print("Refuse friend invite endpoint called")
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422

        result, status = AuthController.refuse_friend_invite(email, invite_id)
        return jsonify(result), status

    except Exception as e:
        print(f"Refuse friend invite route error: {str(e)}")
        return jsonify({
            "status": "1",
            "message": "Failed to refuse invitation",
                "message_code": "REFUSE_INVITATION_FAILED"
        }), 500

@auth_bp.delete("/friend/remove")
@jwt_required()
def remove_friends():
    print("Remove friends endpoint called")
    try:
        email = get_jwt_identity()
        if not isinstance(email, str):
            return jsonify({
                "status": "1",
                "message": "Invalid user identification",
                "message_code": "INVALID_USER_ID"
            }), 422

        data = request.get_json(silent=True) or {}
        ids = data.get("ids[]", [])

        result, status = AuthController.remove_friends(email, ids)
        return jsonify(result), status

    except Exception as e:
        print(f"Remove friends route error: {str(e)}")
        return jsonify({
            "status": "1",
            "message": "Failed to remove friend",
                "message_code": "REMOVE_FRIEND_FAILED"
        }), 500
    








@auth_bp.get("/debug/friends")
@jwt_required()
def debug_friends():
    try:
        email = get_jwt_identity()
        result, status = AuthController.debug_user_friends(email)
        return jsonify(result), status
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    



@auth_bp.post("/friends/default")
@jwt_required()
def create_default_friends():
    try:
        email = get_jwt_identity()
        result, status = AuthController.create_default_friends_for_user(email)
        return jsonify(result), status
    except Exception as e:
        return jsonify({"error": str(e)}), 500