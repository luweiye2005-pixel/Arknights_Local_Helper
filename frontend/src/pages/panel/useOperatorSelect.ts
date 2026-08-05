import { useState, useCallback, useMemo } from "react";
import { message } from "antd";
import { useSearcher } from "../../hooks/useSearcher";
import {
  getOperator,
  getOperatorSkills,
  searchOperators,
  OperatorSkill,
} from "../../api/client";
import { maxEliteForOperator, maxLevelForElite } from "../../utils/operatorCaps";
import { skillAutofill } from "../../utils/skillAutofill";
import { selectEffectiveTalents } from "../../utils/moduleEffects";
import { errorMessage } from "../../utils/errorMessage";
import type { OperatorDetail } from "../../types/panel";

export function useOperatorSelect() {
  const [operatorId, setOperatorId] = useState<string>();
  const [operator, setOperator] = useState<OperatorDetail>();
  const [operatorSkills, setOperatorSkills] = useState<OperatorSkill[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState<string>();
  const [selectedSkillLevel, setSelectedSkillLevel] = useState(7);
  const [moduleId, setModuleId] = useState<string>();
  const [moduleLevel, setModuleLevel] = useState(3);

  const opSearch = useSearcher(async (q: string) => {
    try {
      const items = await searchOperators(q, 50);
      return (items || []).map((op) => ({
        value: op.id,
        label: `${op.name} ${op.rarity}★`,
      }));
    } catch (error) {
      message.error(errorMessage(error, "干员搜索失败"));
      return [];
    }
  });

  const maxElite = useMemo(
    () => (operator ? maxEliteForOperator(operator.phases?.length, operator.rarity) : 2),
    [operator],
  );
  const maxLevel = useMemo(() => {
    const elite = maxElite;
    const phaseMax = operator?.phases?.[elite]?.max_level;
    return operator ? maxLevelForElite(operator.rarity, elite, phaseMax) : 90;
  }, [operator, maxElite]);

  const pickOperator = useCallback(
    async (id: string) => {
      try {
        setOperator(undefined);
        setOperatorSkills([]);
        setSelectedSkillId(undefined);
        setModuleId(undefined);
        const op = await getOperator(id);
        setOperator(op);
        setOperatorId(id);
        const skills = await getOperatorSkills(id);
        setOperatorSkills(skills);
        if (skills.length > 0) {
          setSelectedSkillId(skills[0].skill_id);
          setSelectedSkillLevel(7);
        }
      } catch (error) {
        message.error(errorMessage(error, "获取干员详情失败"));
      }
    },
    [],
  );

  const effectiveTalents = useMemo(
    () => (operator ? selectEffectiveTalents(operator.talents) : []),
    [operator],
  );

  return {
    operatorId, setOperatorId,
    operator, setOperator,
    operatorSkills, setOperatorSkills,
    selectedSkillId, setSelectedSkillId,
    selectedSkillLevel, setSelectedSkillLevel,
    moduleId, setModuleId,
    moduleLevel, setModuleLevel,
    opSearch, pickOperator,
    maxElite, maxLevel,
    effectiveTalents,
  };
}
