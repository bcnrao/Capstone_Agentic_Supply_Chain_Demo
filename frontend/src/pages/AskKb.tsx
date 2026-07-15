import { useState } from "react";
import { Alert, Button, Card, Input, Space, Spin, Typography } from "antd";

import { useAsk } from "../api/hooks";

const { Paragraph } = Typography;
const { TextArea } = Input;

const DEFAULT_QUESTION =
  "Which suppliers and lanes are exposed to Shanghai weather disruption?";

export default function AskKb() {
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const ask = useAsk();

  return (
    <Card title="Ask the local knowledge base" size="small">
      <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        <TextArea
          rows={3}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about suppliers, lanes, facilities, or mitigation playbooks"
        />
        <Button
          type="primary"
          loading={ask.isPending}
          disabled={!question.trim()}
          onClick={() => ask.mutate(question)}
        >
          Ask
        </Button>

        {ask.isPending && <Spin />}
        {ask.isError && (
          <Alert type="error" message="Failed to reach the knowledge base." />
        )}
        {ask.data && (
          <Card size="small" type="inner" title="Answer">
            {ask.data.split("\n").map((line, index) => (
              <Paragraph key={index} style={{ marginBottom: 4 }}>
                {line}
              </Paragraph>
            ))}
          </Card>
        )}
      </Space>
    </Card>
  );
}
