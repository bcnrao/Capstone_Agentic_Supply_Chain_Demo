import { useEffect, useMemo, useState } from "react";
import {
  App,
  Button,
  Checkbox,
  Descriptions,
  Form,
  Input,
  Modal,
  Spin,
  Tabs,
} from "antd";

import { client } from "../api/client";
import { useSaveConfig } from "../api/hooks";
import type { ConfigField, ConfigSnapshot } from "../types/state";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function ConfigModal({ open, onClose }: Props) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [snapshot, setSnapshot] = useState<ConfigSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const save = useSaveConfig();

  const loadSnapshot = async () => {
    setLoading(true);
    try {
      const { data } = await client.get<ConfigSnapshot>("/config");
      setSnapshot(data);
      const values: Record<string, unknown> = {};
      for (const field of data.fields) {
        values[field.name] =
          field.kind === "bool" ? Boolean(field.value) : (field.value ?? "");
      }
      form.setFieldsValue(values);
    } catch {
      message.error("Failed to load configuration");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadSnapshot();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const sections = useMemo(() => {
    const grouped = new Map<string, ConfigField[]>();
    for (const field of snapshot?.fields ?? []) {
      const list = grouped.get(field.section) ?? [];
      list.push(field);
      grouped.set(field.section, list);
    }
    return grouped;
  }, [snapshot]);

  const handleSave = async () => {
    const values = form.getFieldsValue();
    try {
      const result = await save.mutateAsync(values);
      setSnapshot(result);
      message.success("Saved local-first configuration");
    } catch {
      message.error("Failed to save configuration");
    }
  };

  return (
    <Modal
      title="Config"
      open={open}
      width={920}
      onCancel={onClose}
      footer={[
        <Button key="reload" onClick={loadSnapshot} disabled={loading}>
          Reload values
        </Button>,
        <Button key="close" onClick={onClose}>
          Close
        </Button>,
        <Button
          key="save"
          type="primary"
          loading={save.isPending}
          onClick={handleSave}
        >
          Save config
        </Button>,
      ]}
    >
      {loading || !snapshot ? (
        <Spin />
      ) : (
        <>
          <Form form={form} layout="vertical">
            <Tabs
              items={[...sections.entries()].map(([section, fields]) => ({
                key: section,
                label: section,
                children: fields.map((field) =>
                  field.kind === "bool" ? (
                    <Form.Item
                      key={field.name}
                      name={field.name}
                      valuePropName="checked"
                    >
                      <Checkbox>{field.label}</Checkbox>
                    </Form.Item>
                  ) : (
                    <Form.Item key={field.name} name={field.name} label={field.label}>
                      {field.secret ? (
                        <Input.Password autoComplete="off" />
                      ) : (
                        <Input autoComplete="off" />
                      )}
                    </Form.Item>
                  ),
                ),
              }))}
            />
          </Form>

          <Descriptions
            title="Resolved runtime"
            column={{ xs: 1, sm: 2 }}
            size="small"
            bordered
          >
            <Descriptions.Item label="Config file">
              {snapshot.runtime.config_file}
            </Descriptions.Item>
            <Descriptions.Item label="Storage">
              {snapshot.runtime.storage_mode} ({snapshot.runtime.storage_detail})
            </Descriptions.Item>
            <Descriptions.Item label="Database URL">
              {snapshot.runtime.database_url || "-"}
            </Descriptions.Item>
            <Descriptions.Item label="LLM mode">
              {snapshot.runtime.llm_mode}
            </Descriptions.Item>
            <Descriptions.Item label="Retrieval mode">
              {snapshot.runtime.retrieval_mode}
            </Descriptions.Item>
            <Descriptions.Item label="Data home">
              {snapshot.runtime.data_dir}
            </Descriptions.Item>
          </Descriptions>
        </>
      )}
    </Modal>
  );
}
