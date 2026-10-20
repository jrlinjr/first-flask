"""
健康記錄（都存在 diary 表，用 type 欄位區分）：
血糖 blood_sugar、血壓 blood_pressure、體重 weight、飲食 diet

每個方法都回傳 (回應內容 dict, HTTP 狀態碼)，由 controller 負責 jsonify。
"""
import json
from datetime import datetime

from models.user import User
from models.diary import Diary
from utils.api_response import success_body, error_body
from utils.extensions import db
from utils.logger import logger
from utils.time_utils import now_taiwan, parse_recorded_at

# 新增體重時沒有傳身高，就用這個值算 BMI（公分）
DEFAULT_HEIGHT_CM = 170

RECORDED_AT_FORMAT_ERROR = ("Invalid recorded_at format, should be YYYY-MM-DD HH:MM:SS", "INVALID_RECORDED_AT_FORMAT")


class RecordService:

    @staticmethod
    def get_diary_entries(email: str, date: str | None = None):
        """取得日記（所有記錄），可用 date=YYYY-MM-DD 篩選某一天"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            query = Diary.query.filter_by(user_id=user.id)

            if date:
                try:
                    target_date = datetime.strptime(date, "%Y-%m-%d").date()
                    query = query.filter(db.func.date(Diary.recorded_at) == target_date)
                except ValueError:
                    return error_body("Date format error, should be YYYY-MM-DD", "INVALID_DATE_FORMAT"), 400

            diary_records = query.order_by(Diary.recorded_at.desc()).all()

            diary_list = []
            for diary in diary_records:
                # tag / image / location 存的是 JSON，可能是字串要再解析一次
                tag_raw = json.loads(diary.tag) if isinstance(diary.tag, str) else diary.tag
                tag_array = [tag_raw] if isinstance(tag_raw, dict) else tag_raw

                image_array = json.loads(diary.image) if isinstance(diary.image, str) else diary.image

                # 血糖 / 血壓 / 體重記錄沒有 location（NULL），改用空 dict
                location_data = json.loads(diary.location) if isinstance(diary.location, str) else diary.location
                if location_data is None:
                    location_data = {}

                diary_list.append({
                    "id": diary.id,
                    "user_id": diary.user_id,
                    "systolic": diary.systolic,
                    "diastolic": diary.diastolic,
                    "pulse": diary.pulse,
                    "weight": diary.weight,
                    "body_fat": diary.body_fat,
                    "bmi": diary.bmi,
                    "sugar": diary.sugar,
                    "exercise": diary.exercise,
                    "drug": diary.drug,
                    "timeperiod": diary.timeperiod,
                    "description": diary.description,
                    "meal": diary.meal,
                    "tag": tag_array,
                    "image": image_array,
                    "location": {
                        "lat": str(location_data.get("lat", "")),
                        "lng": str(location_data.get("lng", "")),
                    },
                    "reply": diary.reply,
                    "recorded_at": diary.recorded_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": diary.type,
                })

            return success_body(diary=diary_list), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得日記失敗：{e}")
            return error_body("Failed to get diary entries", "GET_DIARY_FAILED"), 500

    @staticmethod
    def get_user_records(email: str, diet=None):
        """取得最新一筆的血糖、血壓、體重；diet 有傳就只看該時段（timeperiod）"""
        logger.info(f"[帳號:{email}] 取得最新健康記錄")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            if diet is not None:
                try:
                    diet = int(diet)
                except (ValueError, TypeError):
                    return error_body("Diet parameter must be an integer", "DIET_MUST_BE_INTEGER"), 400

            query = Diary.query.filter_by(user_id=user.id)
            if diet is not None:
                query = query.filter(Diary.timeperiod == diet)

            # 最新的在前
            records = query.order_by(Diary.recorded_at.desc()).all()

            blood_sugars = {"sugar": 0.0}
            blood_pressures = {"systolic": 0, "diastolic": 0, "pulse": 0}
            weights = {"weight": 0.0}

            for record in records:
                # 最新的血糖
                if record.sugar is not None and record.sugar > 0 and blood_sugars["sugar"] == 0.0:
                    blood_sugars["sugar"] = float(record.sugar)

                # 最新的血壓
                if record.systolic is not None and record.systolic > 0 and blood_pressures["systolic"] == 0:
                    blood_pressures["systolic"] = int(record.systolic)
                    blood_pressures["diastolic"] = int(record.diastolic or 0)
                    blood_pressures["pulse"] = int(record.pulse or 0)

                # 最新的體重
                if record.weight is not None and record.weight > 0 and weights["weight"] == 0.0:
                    weights["weight"] = float(record.weight)

                # 三種都找到了就提早結束
                if blood_sugars["sugar"] > 0 and blood_pressures["systolic"] > 0 and weights["weight"] > 0:
                    break

            return success_body(
                blood_sugars=blood_sugars,
                blood_pressures=blood_pressures,
                weights=weights,
            ), 200

        except Exception as e:
            logger.error(f"[帳號:{email}] 取得最新健康記錄失敗：{e}")
            return error_body("Failed to get health records", "GET_HEALTH_RECORDS_FAILED"), 500

    @staticmethod
    def add_blood_sugar(email: str, sugar, timeperiod=None, recorded_at: str | None = None, drug=None, exercise=None):
        logger.info(f"[帳號:{email}] 新增血糖記錄")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            if sugar is None:
                return error_body("Sugar parameter cannot be empty", "SUGAR_REQUIRED"), 400

            # 血糖值：要是數字，且在 0 ~ 1000 之間
            try:
                sugar = float(sugar)
                if sugar <= 0 or sugar > 1000:
                    return error_body("Invalid blood sugar value", "INVALID_BLOOD_SUGAR"), 400
            except (ValueError, TypeError):
                return error_body("Blood sugar value must be a number", "BLOOD_SUGAR_MUST_BE_NUMBER"), 400

            # 記錄時間：沒傳就用現在
            if recorded_at:
                try:
                    recorded_datetime = parse_recorded_at(recorded_at)
                except ValueError:
                    return error_body(*RECORDED_AT_FORMAT_ERROR), 400
            else:
                recorded_datetime = now_taiwan()

            new_blood_sugar = Diary(
                user_id=user.id,
                sugar=sugar,
                timeperiod=timeperiod or 0,
                drug=drug or 0,
                exercise=exercise or 0,
                type="blood_sugar",
                recorded_at=recorded_datetime,
                created_at=now_taiwan(),
                updated_at=now_taiwan(),
            )
            db.session.add(new_blood_sugar)
            db.session.commit()

            return success_body(new_record_id=new_blood_sugar.id), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 新增血糖記錄失敗：{e}")
            return error_body("Failed to add blood sugar record", "ADD_BLOOD_SUGAR_FAILED"), 500

    @staticmethod
    def add_weight(email: str, weight, bmi=None, body_fat=None, height=DEFAULT_HEIGHT_CM, recorded_at: str | None = None):
        """
        新增體重記錄

        Args:
            weight: 體重（kg，必填）
            bmi: BMI（沒傳就用身高自動算）
            body_fat: 體脂肪率（可選）
            height: 身高（cm，用來算 BMI）
            recorded_at: 記錄時間（YYYY-MM-DD HH:MM:SS）
        """
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            try:
                height = float(height)
                if height <= 0 or height > 300:
                    return error_body("Invalid height parameter", "INVALID_HEIGHT"), 400

                if weight is None:
                    return error_body("Weight parameter cannot be empty", "WEIGHT_REQUIRED"), 400

                weight = float(weight)
                if weight <= 0 or weight > 500:
                    return error_body("Invalid weight parameter", "INVALID_WEIGHT"), 400

                if bmi is not None:
                    bmi = float(bmi)
                    if bmi <= 0 or bmi > 100:
                        return error_body("Invalid BMI parameter", "INVALID_BMI"), 400
                else:
                    # BMI = 體重(kg) / 身高(m) 的平方
                    bmi = round(weight / ((height / 100) ** 2), 2)

                if body_fat is not None:
                    body_fat = float(body_fat)
                    if body_fat < 0 or body_fat > 100:
                        return error_body("Invalid body fat parameter", "INVALID_BODY_FAT"), 400
                else:
                    body_fat = 0.0

            except (ValueError, TypeError):
                return error_body("Parameter type error", "PARAMETER_TYPE_ERROR"), 400

            if recorded_at:
                try:
                    recorded_datetime = parse_recorded_at(recorded_at)
                except ValueError:
                    return error_body(*RECORDED_AT_FORMAT_ERROR), 400
            else:
                recorded_datetime = now_taiwan()

            new_diary = Diary(
                user_id=user.id,
                weight=weight,
                body_fat=body_fat,
                bmi=bmi,
                type="weight",
                recorded_at=recorded_datetime,
                created_at=now_taiwan(),
                updated_at=now_taiwan(),
            )
            db.session.add(new_diary)
            db.session.commit()

            return success_body(new_record_id=new_diary.id), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 新增體重記錄失敗：{e}")
            return error_body("Failed to add weight record", "ADD_WEIGHT_FAILED"), 500

    @staticmethod
    def add_blood_pressure(email: str, systolic, diastolic, pulse, recorded_at: str | None = None):
        """新增血壓記錄（收縮壓、舒張壓、脈搏都必填）"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            if systolic is None or diastolic is None or pulse is None:
                return error_body("Blood pressure and heart rate parameters cannot be empty", "BP_HR_REQUIRED"), 400

            try:
                systolic = int(systolic)
                diastolic = int(diastolic)
                pulse = int(pulse)
            except (ValueError, TypeError):
                return error_body("Blood pressure and heart rate must be numbers", "BP_HR_MUST_BE_NUMBER"), 400

            if systolic <= 0 or diastolic <= 0 or pulse <= 0:
                return error_body("Invalid blood pressure or heart rate values", "INVALID_BP_HR"), 400

            if recorded_at:
                try:
                    recorded_datetime = parse_recorded_at(recorded_at)
                except ValueError:
                    return error_body(*RECORDED_AT_FORMAT_ERROR), 400
            else:
                recorded_datetime = now_taiwan()

            new_pressure = Diary(
                user_id=user.id,
                systolic=systolic,
                diastolic=diastolic,
                pulse=pulse,
                type="blood_pressure",
                recorded_at=recorded_datetime,
                created_at=now_taiwan(),
                updated_at=now_taiwan(),
            )
            db.session.add(new_pressure)
            db.session.commit()

            return success_body(new_record_id=new_pressure.id), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 新增血壓記錄失敗：{e}")
            return error_body("Failed to add blood pressure record", "ADD_BLOOD_PRESSURE_FAILED"), 500

    @staticmethod
    def add_diet_record(email: str, description: str, meal: int, tag, image, lat, lng, recorded_at: str | None):
        """新增飲食記錄；記錄時間格式不對時直接用現在時間"""
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            if recorded_at:
                try:
                    recorded_datetime = parse_recorded_at(recorded_at)
                except Exception:
                    recorded_datetime = now_taiwan()
            else:
                recorded_datetime = now_taiwan()

            # tag 一律存成 JSON 陣列字串
            if isinstance(tag, list):
                tag_json = json.dumps(tag, ensure_ascii=False)
            else:
                tag_json = json.dumps([str(tag)], ensure_ascii=False)

            location_json = json.dumps({"lat": lat, "lng": lng}, ensure_ascii=False)

            new_diary = Diary(
                user_id=user.id,
                description=description,
                meal=meal,
                tag=tag_json,
                image=image,
                location=location_json,
                recorded_at=recorded_datetime,
                type="diet",
                created_at=now_taiwan(),
                updated_at=now_taiwan(),
            )
            db.session.add(new_diary)
            db.session.commit()

            # image_url 之後由前端或其他服務產生，這裡先回空字串
            return success_body(image_url=""), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 新增飲食記錄失敗：{e}")
            return error_body("Failed to add diet record", "ADD_DIET_FAILED"), 500

    @staticmethod
    def delete_user_records(email: str, delete_ids):
        """
        批次刪除健康記錄（只會刪到自己的）

        delete_ids 支援兩種格式：
            [1, 2, 3]
            {"blood_sugars": [1], "weights": [2]}
        """
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                return error_body("User not found", "USER_NOT_FOUND"), 404

            # 字典格式：把每一類的 id 合併成一個 list
            if isinstance(delete_ids, dict):
                merged_ids = []
                for value in delete_ids.values():
                    if isinstance(value, list):
                        merged_ids.extend(value)
                    elif isinstance(value, (str, int)):
                        merged_ids.append(value)
                delete_ids = merged_ids

            if not isinstance(delete_ids, list) or not delete_ids:
                return error_body("Delete IDs must be a non-empty list", "INVALID_DELETE_IDS"), 400

            for record_id in delete_ids:
                if not str(record_id).isdigit():
                    return error_body("All IDs must be valid numbers", "INVALID_ID_FORMAT"), 400

            int_ids = []
            for record_id in delete_ids:
                int_ids.append(int(record_id))

            # 直接在資料庫一次批量刪除（條件有 user_id，所以刪不到別人的）
            deleted_count = Diary.query.filter(
                Diary.user_id == user.id,
                Diary.id.in_(int_ids),
            ).delete(synchronize_session=False)
            db.session.commit()

            return success_body(deleted_count=deleted_count), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"[帳號:{email}] 刪除健康記錄失敗：{e}")
            return error_body("Failed to delete health records", "DELETE_HEALTH_RECORDS_FAILED"), 500
