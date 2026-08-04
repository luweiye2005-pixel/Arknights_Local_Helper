import { Col, Divider, Form, InputNumber, Row, Typography } from "antd";
import type { Dispatch, SetStateAction } from "react";
import type { EnemyManual } from "../../types/panel";

const { Paragraph } = Typography;

type Props = {
  value: EnemyManual;
  onChange: Dispatch<SetStateAction<EnemyManual>>;
};

const fields: { key: keyof EnemyManual; label: string }[] = [
  { key: "atk_pct", label: "敌人攻击+%" },
  { key: "atk_flat", label: "敌人攻击定值" },
  { key: "def_pct", label: "敌人防御+%" },
  { key: "def_flat", label: "敌人防御定值" },
  { key: "hp_pct", label: "敌人生命+%" },
  { key: "hp_flat", label: "敌人生命定值" },
  { key: "res_pct", label: "敌人法抗+%" },
  { key: "res_flat", label: "敌人法抗定值" },
];

export default function EnemyStatsSection({ value, onChange }: Props) {
  return (
    <>
      <Divider>敌人面板调整</Divider>
      <Paragraph type="secondary" style={{ marginBottom: 8 }}>
        技能对敌人的减益会自动填入；也可手改。百分比与定值可负（如防御-60%、法抗-30%）。
      </Paragraph>
      {[fields.slice(0, 4), fields.slice(4)].map((row, rowIndex) => (
        <Row gutter={12} key={rowIndex}>
          {row.map((field) => (
            <Col span={6} key={field.key}>
              <Form.Item label={field.label}>
                <InputNumber
                  style={{ width: "100%" }}
                  value={value[field.key]}
                  onChange={(next) =>
                    onChange((previous) => ({
                      ...previous,
                      [field.key]: Number(next) || 0,
                    }))
                  }
                />
              </Form.Item>
            </Col>
          ))}
        </Row>
      ))}
    </>
  );
}
