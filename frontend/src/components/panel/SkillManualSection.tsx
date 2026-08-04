import { Col, Divider, Form, InputNumber, Row, Typography } from "antd";
import type { Dispatch, SetStateAction } from "react";
import type { SkillManual } from "../../types/panel";

const { Paragraph } = Typography;

type Props = {
  value: SkillManual;
  onChange: Dispatch<SetStateAction<SkillManual>>;
};

export default function SkillManualSection({ value, onChange }: Props) {
  const setNumber = (field: keyof SkillManual, next: number | null) => {
    onChange((previous) => ({ ...previous, [field]: Number(next) || 0 }));
  };

  return (
    <>
      <Divider>技能 / 伤害手填</Divider>
      <Paragraph type="secondary" style={{ marginBottom: 8 }}>
        「攻击力+X%」为直接乘算（与藏品ATK%加算）；多个「提升至」相乘。例：维什戴尔专三填攻击+180、提升至125与220。
      </Paragraph>
      <Row gutter={12}>
        {[
          ["atk_pct", "技能攻击力+%"],
          ["hp_pct", "技能生命+%"],
          ["def_pct", "技能防御+%"],
          ["aspd", "技能攻速"],
          ["res_flat", "技能法抗+"],
        ].map(([field, label]) => (
          <Col span={field === "aspd" ? 4 : 5} key={field}>
            <Form.Item label={label}>
              <InputNumber
                style={{ width: "100%" }}
                value={value[field as keyof SkillManual] as number}
                onChange={(next) => setNumber(field as keyof SkillManual, next)}
              />
            </Form.Item>
          </Col>
        ))}
      </Row>
      <Row gutter={12}>
        <Col span={6}>
          <Form.Item label="技能法抗+%">
            <InputNumber
              style={{ width: "100%" }}
              value={value.res_pct}
              onChange={(next) => setNumber("res_pct", next)}
            />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item label="提升至%（天赋）">
            <InputNumber
              style={{ width: "100%" }}
              min={0}
              placeholder="如 125"
              value={value.scale_to_1 || undefined}
              onChange={(next) => setNumber("scale_to_1", next)}
            />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item label="提升至%（技能）">
            <InputNumber
              style={{ width: "100%" }}
              min={0}
              placeholder="如 220"
              value={value.scale_to_2 || undefined}
              onChange={(next) => setNumber("scale_to_2", next)}
            />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item label="造成攻击力%">
            <InputNumber
              style={{ width: "100%" }}
              min={0}
              value={value.damage_scale_pct ?? undefined}
              onChange={(next) =>
                onChange((previous) => ({
                  ...previous,
                  damage_scale_pct: next == null ? null : Number(next),
                }))
              }
            />
          </Form.Item>
        </Col>
      </Row>
    </>
  );
}
