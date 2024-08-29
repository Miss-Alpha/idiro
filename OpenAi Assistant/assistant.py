
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


# Step 1: Create a new Assistant with File Search Enabled
# ----------------------------------------------------------------
client = OpenAI()
assistant = client.beta.assistants.create(
  name="Financial Analyst Assistant",
  instructions="You are an expert financial analyst. Use you knowledge base to answer questions about audited financial statements.",
  tools=[{"type": "file_search"}], #code_interpreter / file_search / function
  model="gpt-4o",
)

# Create a vector store caled "Financial Statements"
vector_store = client.beta.vector_stores.create(name="Financial Statements")

# Step 2: Ready the files for upload to OpenAI
# ----------------------------------------------------------------
file_paths = ["OpenAi Assistant/Central Bank of Ireland policy-on-receipt-of-business-hospitality-and-gifts.pdf", "OpenAi Assistant/MasterCard Gifts and Hospitality Policy 933.pdf"]
file_streams = [open(path, "rb") for path in file_paths]
 
# Use the upload and poll SDK helper to upload the files, add them to the vector store,
# and poll the status of the file batch for completion.
file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
  vector_store_id=vector_store.id, files=file_streams
)

# Step 3: You can print the status and the file counts of the batch to see the result of this operation.
# ----------------------------------------------------------------
print(file_batch.status)
print(file_batch.file_counts)


# Update the assistant to use the new Vector Store
assistant = client.beta.assistants.update(
  assistant_id=assistant.id,
  tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
)

# Step 4: Create a thread
# ----------------------------------------------------------------
# Upload the user provided file to OpenAI
message_file = client.files.create(
  file=open("OpenAi Assistant/MasterCard Gifts and Hospitality Policy 933.pdf", "rb"), purpose="assistants"
)
 
# Create a thread and attach the file to the message
thread = client.beta.threads.create(
  messages=[
    {
      "role": "user",
      "content": "What are the approval levels to give a gift to A Government Official",
      # Attach the new file to the message.
      "attachments": [
        { "file_id": message_file.id, "tools": [{"type": "file_search"}] }
      ],
    }
  ]
)
 
# The thread now has a vector store with that file in its tool resources.
print(thread.tool_resources.file_search)


# Step 5: Create a run and check the output
# ----------------------------------------------------------------
from typing_extensions import override
from openai import AssistantEventHandler, OpenAI
 
client = OpenAI()
 
class EventHandler(AssistantEventHandler):
    @override
    def on_text_created(self, text) -> None:
        print(f"\nassistant > ", end="", flush=True)

    @override
    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    @override
    def on_message_done(self, message) -> None:
        # print a citation to the file searched
        message_content = message.content[0].text
        annotations = message_content.annotations
        citations = []
        for index, annotation in enumerate(annotations):
            message_content.value = message_content.value.replace(
                annotation.text, f"[{index}]"
            )
            if file_citation := getattr(annotation, "file_citation", None):
                cited_file = client.files.retrieve(file_citation.file_id)
                citations.append(f"[{index}] {cited_file.filename}")

        print('Response:')
        print(message_content.value)
        print('Citation:')
        print("\n".join(citations))


# Then, we use the stream SDK helper
# with the EventHandler class to create the Run
# and stream the response.

with client.beta.threads.runs.stream(
    thread_id=thread.id,
    assistant_id=assistant.id,
    instructions="Please address the user as Jane Doe. The user has a premium account.",
    event_handler=EventHandler(),
) as stream:
    stream.until_done()