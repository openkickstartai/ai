#!/usr/bin/env python3
"""
AI食物过敏预警器 - 核心检测引擎
救生级AI应用，为过敏症患者提供实时食物安全检测
"""

import re
import json
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum
import sqlite3
import os


class RiskLevel(Enum):
    """过敏风险等级"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


class AllergenType(Enum):
    """过敏原类型"""
    PEANUT = "peanut"
    TREE_NUT = "tree_nut"
    SHELLFISH = "shellfish"
    FISH = "fish"
    DAIRY = "dairy"
    GLUTEN = "gluten"
    SOY = "soy"
    EGG = "egg"
    SESAME = "sesame"
    SULFITES = "sulfites"


@dataclass
class DetectionResult:
    """检测结果"""
    ingredients: List[str]
    detected_allergens: List[Dict]
    risk_level: RiskLevel
    confidence: float
    safe: bool
    warnings: List[str]


class AllergenDatabase:
    """过敏原数据库"""
    
    def __init__(self, db_path: str = "data/allergen_db.sqlite"):
        self.db_path = db_path
        self._init_database()
        
    def _init_database(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allergens (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                type TEXT,
                severity INTEGER,
                aliases TEXT,
                languages TEXT
            )
        """)
        
        self._populate_base_data()
        conn.commit()
        conn.close()
        
    def _populate_base_data(self):
        """填充基础过敏原数据"""
        base_allergens = [
            ("peanuts", "peanut", 5, "peanut,groundnut,arachis hypogaea,花生,落花生", "en:peanuts,zh:花生"),
            ("milk", "dairy", 3, "milk,dairy,lactose,casein,奶,牛奶,乳制品", "en:milk,zh:牛乳"),
            ("gluten", "gluten", 3, "gluten,wheat,flour,麸质,小麦,面粉", "en:gluten,zh:麸质"),
            ("shrimp", "shellfish", 5, "shrimp,prawn,crustacean,虾,海鲜", "en:shrimp,zh:虾"),
            ("eggs", "egg", 3, "egg,ovalbumin,ovomucoid,蛋,鸡蛋", "en:eggs,zh:鸡蛋")
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for allergen in base_allergens:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO allergens 
                    (name, type, severity, aliases, languages)
                    VALUES (?, ?, ?, ?, ?)
                """, allergen)
            except sqlite3.IntegrityError:
                continue
                
        conn.commit()
        conn.close()
        
    def search_allergens(self, ingredient: str) -> List[Dict]:
        """搜索成分中的过敏原"""
        ingredient = ingredient.lower().strip()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name, type, severity, aliases, languages FROM allergens
            WHERE LOWER(name) LIKE ? OR LOWER(aliases) LIKE ?
        """, (f"%{ingredient}%", f"%{ingredient}%"))
        
        rows = cursor.fetchall()
        
        allergens = []
        for row in rows:
            allergens.append({
                "name": row[0],
                "type": row[1],
                "severity": row[2],
                "aliases": row[3].split(",") if row[3] else [],
                "languages": row[4] if row[4] else {}
            })
            
        conn.close()
        return allergens


class IngredientProcessor:
    """成分处理器"""
    
    def __init__(self):
        self.separators = r"[,，;；、\n]\s*"
        self.stop_words = {
            "ingredients", "成分", "原料", "材料", "contains", "含有",
            "water", "水", "salt", "盐", "sugar", "糖", "oil", "油",
            "natural", "自然", "artificial", "人工", "flavor", "风味",
            "preservative", "防腐剂", "color", "色素", "vitamin", "维生素"
        }
        
    def extract_ingredients(self, text: str) -> List[str]:
        """从文本中提取成分列表"""
        if not text:
            return []
            
        text = self._clean_text(text)
        ingredients = re.split(self.separators, text)
        
        cleaned_ingredients = []
        for ingredient in ingredients:
            cleaned = self._clean_ingredient(ingredient)
            if cleaned and len(cleaned) > 1:
                cleaned_ingredients.append(cleaned)
                
        return cleaned_ingredients
        
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        text = re.sub(r"\s+", " ", text)
        
        patterns_to_remove = [
            r"ingredients?[:：]\s*",
            r"contains?[:：]\s*",
            r"may contain[:：]\s*"
        ]
        
        for pattern in patterns_to_remove:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            
        return text.strip()
        
    def _clean_ingredient(self, ingredient: str) -> str:
        """清理单个成分"""
        ingredient = ingredient.lower().strip()
        ingredient = re.sub(r"\d+%?", "", ingredient)
        ingredient = re.sub(r"\([^)]*\)", "", ingredient)
        
        prefixes_to_remove = ["contains", "contains*", "may contain", "+"]
        for prefix in prefixes_to_remove:
            if ingredient.startswith(prefix):
                ingredient = ingredient[len(prefix):].strip()
                
        if ingredient in self.stop_words:
            return ""
            
        return ingredient


class RiskAssessor:
    """风险评估器"""
    
    def __init__(self, user_allergens: Dict[str, int] = None):
        self.user_allergens = user_allergens or {}
        
    def assess_risk(self, detected_allergens: List[Dict]) -> RiskLevel:
        """评估过敏风险等级"""
        if not detected_allergens:
            return RiskLevel.LOW
            
        max_risk = RiskLevel.LOW
        
        for allergen in detected_allergens:
            if allergen["type"] in self.user_allergens:
                user_severity = self.user_allergens[allergen["type"]]
                allergen_severity = allergen["severity"]
                
                combined_severity = min(user_severity + allergen_severity, 10)
                
                if combined_severity >= 8:
                    max_risk = RiskLevel.SEVERE
                elif combined_severity >= 6:
                    max_risk = RiskLevel.HIGH
                elif combined_severity >= 4:
                    max_risk = RiskLevel.MODERATE
                    
        return max_risk
        
    def generate_warnings(self, detected_allergens: List[Dict]) -> List[str]:
        """生成警告信息"""
        warnings = []
        
        for allergen in detected_allergens:
            if allergen["type"] in self.user_allergens:
                user_severity = self.user_allergens[allergen["type"]]
                
                if user_severity >= 4 and allergen["severity"] >= 4:
                    warnings.append(f"⚠️ 严重警告：检测到{allergen[\"name\"]}，可能导致严重过敏反应")
                elif user_severity >= 3 or allergen["severity"] >= 3:
                    warnings.append(f"🔔 警告：检测到{allergen[\"name\"]}，需谨慎食用")
                else:
                    warnings.append(f"💡 提醒：检测到{allergen[\"name\"]}，轻度过敏原")
                    
        return warnings


class AllergenDetector:
    """过敏原检测器主类"""
    
    def __init__(self, user_allergens: Dict[str, int] = None):
        self.ingredient_processor = IngredientProcessor()
        self.allergen_db = AllergenDatabase()
        self.risk_assessor = RiskAssessor(user_allergens)
        
    def scan_text(self, text: str) -> DetectionResult:
        """直接分析文本"""
        ingredients = self.ingredient_processor.extract_ingredients(text)
        return self._analyze_ingredients(ingredients)
        
    def _analyze_ingredients(self, ingredients: List[str]) -> DetectionResult:
        """分析成分列表中的过敏原"""
        detected_allergens = []
        found_ingredients = []
        
        for ingredient in ingredients:
            found_ingredients.append(ingredient)
            
            matching_allergens = self.allergen_db.search_allergens(ingredient)
            
            for allergen in matching_allergens:
                if not any(a["type"] == allergen["type"] for a in detected_allergens):
                    detected_allergens.append({
                        "name": allergen["name"],
                        "type": allergen["type"],
                        "severity": allergen["severity"],
                        "matched_ingredient": ingredient
                    })
        
        risk_level = self.risk_assessor.assess_risk(detected_allergens)
        warnings = self.risk_assessor.generate_warnings(detected_allergens)
        
        confidence = self._calculate_confidence(detected_allergens, ingredients)
        safe = risk_level == RiskLevel.LOW and len(detected_allergens) == 0
        
        return DetectionResult(
            ingredients=found_ingredients,
            detected_allergens=detected_allergens,
            risk_level=risk_level,
            confidence=confidence,
            safe=safe,
            warnings=warnings
        )
        
    def _calculate_confidence(self, detected_allergens: List[Dict], ingredients: List[str]) -> float:
        """计算检测置信度"""
        if not ingredients:
            return 0.0
            
        total_ingredients = len(ingredients)
        matched_ingredients = len(detected_allergens)
        
        if matched_ingredients > 0:
            confidence = 0.6 + (matched_ingredients / total_ingredients) * 0.4
        else:
            if total_ingredients > 5:
                confidence = 0.8
            else:
                confidence = 0.5
                
        return min(confidence, 1.0)


def main():
    """主函数，测试过敏原检测功能"""
    user_allergens = {
        "peanut": 5,  # 严重花生过敏
        "shellfish": 3,  # 中度海鲜过敏
        "dairy": 2  # 轻度乳制品过敏
    }
    
    detector = AllergenDetector(user_allergens)
    
    test_text = """
    Ingredients:
    Wheat flour, sugar, peanuts, milk powder, salt, 
    natural flavors, shrimp powder, preservatives
    """
    
    print("🔍 开始检测过敏原...")
    result = detector.scan_text(test_text)
    
    print(f"\n📋 检测结果:")
    print(f"识别的成分: {result.ingredients}")
    print(f"检测到的过敏原: {result.detected_allergens}")
    print(f"风险等级: {result.risk_level.value}")
    print(f"置信度: {result.confidence:.2f}")
    print(f"是否安全: {\"✅ 安全\" if result.safe else \"❌ 不安全\"}")
    
    if result.warnings:
        print(f"\n⚠️ 警告信息:")
        for warning in result.warnings:
            print(f"  {warning}")


if __name__ == "__main__":
    main()