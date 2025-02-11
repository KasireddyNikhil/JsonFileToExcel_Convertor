import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import webbrowser
import os
import sqlite3
import msvcrt
from tkscrolledframe import ScrolledFrame
import difflib
import re

# Define the list of admin users
ADMIN_USERS = ['519846', '520271', '271652']  # Replace with actual usernames

# Function to get the database path dynamically based on the current user
def get_db_path():
    user = os.getlogin()
    dir_path = f'C:/Users/{user}/Alstom/PRSAA - Documents/Project-REX'
    os.makedirs(dir_path, exist_ok=True)
    db_path = os.path.join(dir_path, 'datas.db')
    return db_path

# Define the shared path for the database and lock file
db_path = get_db_path()
lock_file = db_path + '.lock'

# Function to create the lock file
def create_lock_file():
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)
    with open(lock_file, 'w') as lock:
        lock.write('Application is running.')

# Function to remove the lock file
def remove_lock_file():
    if os.path.exists(lock_file):
        os.remove(lock_file)

# Ensure the lock file is removed on exit
import atexit
atexit.register(remove_lock_file)

def enable_wal_mode():
    with sqlite3.connect(db_path) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.commit()

enable_wal_mode()

def acquire_lock():
    try:
        lock = open(lock_file, 'w')
        msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        return lock
    except IOError as e:
        print(f"Error acquiring lock: {e}")
        # messagebox.showerror("Lock Error", "Could not acquire lock. Please try again.")
        return None

def release_lock(lock):
    if lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()

def initialize_db():
    lock = acquire_lock()
    if lock is None:
        return
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS Sections (
                              id INTEGER PRIMARY KEY,
                              name TEXT NOT NULL,
                              type TEXT NOT NULL)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS Content (
                              id INTEGER PRIMARY KEY,
                              section_id INTEGER,
                              title TEXT NOT NULL,
                              description TEXT,
                              is_appro ved INTEGER DEFAULT 0,
                              user TEXT NOT NULL,
                              is_deleted INTEGER DEFAULT 0,
                              FOREIGN KEY (section_id) REFERENCES Sections(id))''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS PendingContent (
                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                              content_id INTEGER,
                              pending_description TEXT,
                              user TEXT,
                              submission_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                              FOREIGN KEY (content_id) REFERENCES Content(id))''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS DeletionRequests (
                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                              content_id INTEGER,
                              user TEXT,
                              request_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                              FOREIGN KEY (content_id) REFERENCES Content(id))''')
            cursor.execute('''
                            CREATE TABLE IF NOT EXISTS Notifications (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user TEXT ,
                                message TEXT ,
                                is_read INTEGER DEFAULT 0,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                            )''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sections_name ON Sections (name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_title ON Content (title)")
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
        messagebox.showerror("Database Error", "Could not initialize the database. Please try again.")
    finally:
        release_lock(lock)

if not os.path.exists(db_path):
    print("Database file not found. Initializing database.")
    initialize_db()
else:
    print("Database file found. Proceeding with existing database.")
    initialize_db()  # Ensure the database schema is up-to-date

def execute_query(query, params=()):
    lock = acquire_lock()
    if lock is None:
        return
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")
            cursor.execute(query, params)
            conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"An error occurred: {e}")
        messagebox.showerror("Database Error", "An error occurred while executing the query. Please try again.")
    finally:
        release_lock(lock)

def fetch_query(query, params=()):
    lock = acquire_lock()
    if lock is None:
        return []
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        messagebox.showerror("Database Error", "An error occurred while fetching data. Please try again.")
        return []
    finally:
        release_lock(lock)

# Initialize the database
initialize_db()

# Global variables to keep track of the current selections
current_parent_section = None
current_subsection = None
current_section_type = None
is_editing = False

# Dictionary to store hyperlink tag and URLs
hyperlink_ranges = {}

# Function to read data from the database
def read_data(table_name, section_type=None):
    if section_type:
        query = "SELECT * FROM Sections WHERE type = ?"
        return fetch_query(query, (section_type,))
    return fetch_query(f"SELECT * FROM {table_name}")

# Function to search data based on user input and highlight matched items
def search_data(query):
    # Search in sections
    sections = fetch_query("SELECT id, name, type FROM Sections WHERE name LIKE ?", ('%' + query + '%',))
   
    # Search in subsections (Content table)
    subsections = fetch_query("SELECT id, title, section_id FROM Content WHERE title LIKE ? OR description LIKE ?", ('%' + query + '%', '%' + query + '%'))
   
    return sections, subsections

def highlight_matches(sections, subsections):
    # Collect section IDs that need to be highlighted
    section_ids_to_highlight = set(section[0] for section in sections)
    section_ids_to_highlight.update(subsection[2] for subsection in subsections)
   
    # Highlight sections
    all_sections = fetch_query("SELECT id, name, type FROM Sections")
    for section in all_sections:
        listbox = get_listbox(section[2])
        if section[1] in listbox.get(0, tk.END):  # Ensure section name is in listbox
            index = listbox.get(0, tk.END).index(section[1])
            if section[0] in section_ids_to_highlight:
                listbox.itemconfig(index, {'bg': 'yellow'})
            else:
                listbox.itemconfig(index, {'bg': 'white'})

def highlight_subsections(subsections):
    for i in range(subsections_list.size()):
        subsections_list.itemconfig(i, {'bg': 'white'})
    for subsection in subsections:
        try:
            index = subsections_list.get(0, tk.END).index(subsection[1])
            subsections_list.itemconfig(index, {'bg': 'yellow'})
        except ValueError:
            continue

def apply_tags(text_widget, text, query=None):
    text_widget.delete("1.0", tk.END)
    lines = text.split('\n')
    for line in lines:
        # Parse and apply bullet points first
        if line.startswith('- '):
            text_widget.insert(tk.END, '\u2022 ' + line[2:] + '\n')
            continue

        # Parse and apply bold
        while '**' in line:
            start = line.index('**')
            end = line.index('**', start + 2)
            text_widget.insert(tk.END, line[:start])
            text_widget.insert(tk.END, line[start + 2:end], 'bold')
            line = line[end + 2:]

        # Parse and apply italic
        while '*' in line:
            start = line.index('*')
            end = line.index('*', start + 1)
            text_widget.insert(tk.END, line[:start])
            text_widget.insert(tk.END, line[start + 1:end], 'italic')
            line = line[end + 1:]

        # Parse and apply underline
        while '__' in line:
            start = line.index('__')
            end = line.index('__', start + 2)
            text_widget.insert(tk.END, line[:start])
            text_widget.insert(tk.END, line[start + 2:end], 'underline')
            line = line[end + 2:]

        # Parse and apply hyperlinks
        while '[' in line and ']' in line and '(' in line and ')' in line:
            start_text = line.index('[')
            end_text = line.index(']', start_text)
            start_url = line.index('(', end_text)
            end_url = line.index(')', start_url)
            text_widget.insert(tk.END, line[:start_text])
            link_text = line[start_text + 1:end_text]
            text_widget.insert(tk.END, link_text, 'hyperlink')
            link_url = line[start_url + 1:end_url]
            start_index = text_widget.index(tk.END + f"-{len(link_text)+1}c")
            end_index = text_widget.index(tk.END + '-1c')
            hyperlink_ranges[(start_index, end_index)] = link_url
            line = line[end_url + 1:]

        text_widget.insert(tk.END, line + '\n')

    if query:
        start_idx = "1.0"
        while True:
            start_idx = text_widget.search(query, start_idx, nocase=1, stopindex=tk.END)
            if not start_idx:
                break
            end_idx = f"{start_idx}+{len(query)}c"
            text_widget.tag_add('highlight', start_idx, end_idx)
            start_idx = end_idx

        text_widget.tag_config('highlight', background='yellow')

   

def load_content(subsection_name):
    global current_subsection
    current_subsection = subsection_name
    user = os.getlogin()

    content = fetch_query("SELECT id, description, is_approved, user FROM Content WHERE title = ? AND is_deleted = 0", (subsection_name,))

    if content:
        content_id = content[0][0]
        approved_description = content[0][1]
        content_user = content[0][3]

        pending_content = fetch_query("SELECT pending_description, user FROM PendingContent WHERE content_id = ? AND user = ?", (content_id, user))
        deletion_request = fetch_query("SELECT user FROM DeletionRequests WHERE content_id = ? AND user = ?", (content_id, user))

        content_textbox.config(state=tk.NORMAL)
        content_textbox.delete("1.0", tk.END)

        if pending_content:
            content_textbox.insert(tk.END, "Pending edit:\n\n")
            pending_description = pending_content[0][0]
            apply_tags(content_textbox, pending_description, search_entry.get().strip())
        elif deletion_request:
            content_textbox.insert(tk.END, "Pending delete request:\n\n")
            if approved_description:
                apply_tags(content_textbox, approved_description, search_entry.get().strip())
        else:
            if approved_description:
                apply_tags(content_textbox, approved_description, search_entry.get().strip())
            else:
                content_textbox.insert(tk.END, "No approved content available.")
           
        enable_content()
    else:
        content_textbox.config(state=tk.NORMAL)
        content_textbox.delete("1.0", tk.END)
        content_textbox.insert(tk.END, "No content available.")
        disable_content()
    content_textbox.config(state=tk.DISABLED)

def enable_content():
    edit_content_button.config(state=tk.NORMAL)
    delete_content_button.config(state=tk.NORMAL)

def disable_content():
    global is_editing
    is_editing = False
    edit_content_button.config(state=tk.DISABLED)
    delete_content_button.config(state=tk.DISABLED)
    content_textbox.config(state=tk.DISABLED)
    content_textbox.unbind("<Button-3>")

def update_listboxes(event=None):
    query = search_entry.get().strip()
    if query == "":
        reset_listboxes()
    else:
        sections, subsections = search_data(query)
        highlight_matches(sections, subsections)
        content_textbox.config(state=tk.NORMAL)
        content_textbox.delete("1.0", tk.END)
        content_textbox.config(state=tk.DISABLED)



def load_default_subsections_and_content():
    global current_parent_section
    global current_subsection

    current_parent_section = None
    current_subsection = None
    subsections_list.delete(0, tk.END)
    content_textbox.config(state=tk.NORMAL)
    content_textbox.delete("1.0", tk.END)
    content_textbox.config(state=tk.DISABLED)
    disable_subsections()
    disable_content()

def reset_listboxes():
    load_listbox(functions_list, 'Functions')
    load_listbox(design_list, 'Important Design Aspects')
    load_listbox(interfaces_list, 'Interfaces')
    search_entry.delete(0, tk.END)
    load_default_subsections_and_content()


def get_listbox(section_type):
    if section_type == 'Functions':
        return functions_list
    elif section_type == 'Important Design Aspects':
        return design_list
    elif section_type == 'Interfaces':
        return interfaces_list

def get_section_id_by_name(section_name):
    result = fetch_query("SELECT id FROM Sections WHERE name = ?", (section_name,))
    return result[0][0] if result else None

def load_listbox(listbox, section_type, data=None):
    listbox.delete(0, tk.END)
    data = data if data is not None else read_data('Sections', section_type)
    for item in data:
        if len(item) > 1:
            listbox.insert(tk.END, item[1])  # Assuming the second column contains the name
        else:
            listbox.insert(tk.END, item[0])
    listbox.bind('<<ListboxSelect>>', on_select)

def load_subsections(parent_name):
    global current_parent_section
    global current_section_type
    current_parent_section = parent_name
    parent_id = get_section_id_by_name(parent_name)
    query = "SELECT type FROM Sections WHERE name = ?"
    current_section_type = fetch_query(query, (parent_name,))[0][0]
    subsections = fetch_query("SELECT id, title FROM Content WHERE section_id = ? AND is_deleted = 0", (parent_id,))
    load_listbox(subsections_list, 'Content', subsections)
    enable_subsections()
    disable_content()  # Disable content buttons initially
 
    queries = search_entry.get().strip()
    print(queries)
    if queries:
        _, subsections = search_data(queries)
        highlight_subsections(subsections)
 

def on_select(event):
    widget = event.widget
    selection = widget.curselection()
    if selection:
        item = widget.get(selection[0])
        if widget in [functions_list, design_list, interfaces_list]:
            load_subsections(item)
            enable_subsections()
            content_textbox.config(state=tk.NORMAL)
            content_textbox.delete("1.0", tk.END)
            content_textbox.config(state=tk.DISABLED)
        elif widget == subsections_list:
            load_content(item)
            enable_content()  # Enable content buttons when a subsection is selected

def add_section(section_type):
    def save_new_section():
        new_section_name = new_section_name_entry.get().strip()
        if new_section_name:
            execute_query("INSERT INTO Sections (name, type) VALUES (?, ?)", (new_section_name, section_type))
            load_listbox(get_listbox(section_type), section_type)
            new_section_window.destroy()
        else:
            messagebox.showwarning("Input Error", "Section name is required.")

    new_section_window = tk.Toplevel(root)
    new_section_window.title("Add New Section")

    new_section_name_label = ttk.Label(new_section_window, text="Section Name")
    new_section_name_label.pack(pady=5)
    new_section_name_entry = ttk.Entry(new_section_window, width=50)
    new_section_name_entry.pack(pady=5)

    save_button = ttk.Button(new_section_window, text="Save", command=save_new_section)
    save_button.pack(pady=10)

def edit_section(section_type):
    try:
        selected_section = get_selected_item(get_listbox(section_type))
    except tk.TclError:
        messagebox.showwarning("Selection Error", "Please select a section to edit.")
        return

    def save_edited_section():
        new_section_name = edit_section_name_entry.get().strip()
        if new_section_name:
            section_id = get_section_id_by_name(selected_section)
            execute_query("UPDATE Sections SET name = ? WHERE id = ?", (new_section_name, section_id))
            load_listbox(get_listbox(section_type), section_type)
            edit_section_window.destroy()
        else:
            messagebox.showwarning("Input Error", "Section name is required.")

    edit_section_window = tk.Toplevel(root)
    edit_section_window.title("Edit Section")

    edit_section_name_label = ttk.Label(edit_section_window, text="Section Name")
    edit_section_name_label.pack(pady=5)
    edit_section_name_entry = ttk.Entry(edit_section_window, width=50)
    edit_section_name_entry.insert(0, selected_section)
    edit_section_name_entry.pack(pady=5)

    save_button = ttk.Button(edit_section_window, text="Save", command=save_edited_section)
    save_button.pack(pady=10)

def delete_section(section_type):
    try:
        selected_section = get_selected_item(get_listbox(section_type))
    except tk.TclError:
        messagebox.showwarning("Selection Error", "Please select a section to delete.")
        return

    if messagebox.askyesno("Delete Section", f"Are you sure you want to delete '{selected_section}' and its content?"):
        section_id = get_section_id_by_name(selected_section)
        execute_query("DELETE FROM Sections WHERE id = ?", (section_id,))
        execute_query("DELETE FROM Content WHERE section_id = ?", (section_id,))
        load_listbox(get_listbox(section_type), section_type)

def add_subsection(section_type):
    if current_parent_section is None:
        messagebox.showwarning("Selection Error", "Please select a section to add a subsection.")
        return

    def save_new_subsection():
        new_subsection_title = new_subsection_title_entry.get().strip()
        if new_subsection_title:
            query = """
            INSERT INTO Content (section_id, title, description, is_approved, user)
            VALUES ((SELECT id FROM Sections WHERE name = ? AND type = ?), ?, '', 1, ?)
            """
            execute_query(query, (current_parent_section, section_type, new_subsection_title, os.getlogin()))
            load_subsections(current_parent_section)
            new_subsection_window.destroy()
        else:
            messagebox.showwarning("Input Error", "Title is required.")

    new_subsection_window = tk.Toplevel(root)
    new_subsection_window.title("Add New Subsection")

    new_subsection_title_label = ttk.Label(new_subsection_window, text="Subsection Title")
    new_subsection_title_label.pack(pady=5)
    new_subsection_title_entry = ttk.Entry(new_subsection_window, width=50)
    new_subsection_title_entry.pack(pady=5)

    save_button = ttk.Button(new_subsection_window, text="Save", command=save_new_subsection)
    save_button.pack(pady=10)

def edit_subsection(section_type):
    if current_subsection is None:
        messagebox.showwarning("Selection Error", "Please select a subsection to edit.")
        return

    def save_edited_subsection():
        selected_section = current_parent_section
        new_subsection_title = edit_subsection_title_entry.get().strip()
        if new_subsection_title:
            query = """
            UPDATE Content SET title = ?
            WHERE title = ? AND section_id = (SELECT id FROM Sections WHERE name = ? AND type = ?)
            """
            execute_query(query, (new_subsection_title, current_subsection, selected_section, section_type))
            load_subsections(selected_section)
            edit_subsection_window.destroy()
        else:
            messagebox.showwarning("Input Error", "Title is required.")

    edit_subsection_window = tk.Toplevel(root)
    edit_subsection_window.title("Edit Subsection")

    edit_subsection_title_label = ttk.Label(edit_subsection_window, text="Subsection Title")
    edit_subsection_title_label.pack(pady=5)
    edit_subsection_title_entry = ttk.Entry(edit_subsection_window, width=50)
    edit_subsection_title_entry.insert(0, current_subsection)
    edit_subsection_title_entry.pack(pady=5)

    save_button = ttk.Button(edit_subsection_window, text="Save", command=save_edited_subsection)
    save_button.pack(pady=10)

def delete_subsection(section_type):
    if current_subsection is None:
        messagebox.showwarning("Selection Error", "Please select a subsection to delete.")
        return

    if messagebox.askyesno("Delete Subsection", f"Are you sure you want to delete '{current_subsection}'?"):
        selected_section = current_parent_section
        query = """
        DELETE FROM Content
        WHERE title = ? AND section_id = (SELECT id FROM Sections WHERE name = ? AND type = ?)
        """
        execute_query(query, (current_subsection, selected_section, section_type))
        messagebox.showinfo("Delete Subsection", "Subsection deleted successfully.")
        load_subsections(selected_section)

def edit_content():
    open_edit_window()

def delete_content():
    if current_subsection is None:
        messagebox.showwarning("Selection Error", "Please select content to delete.")
        return

    if messagebox.askyesno("Delete Content", f"Are you sure you want to request deletion for the content of '{current_subsection}'?"):
        selected_section = current_parent_section
        content_id = fetch_query("SELECT id FROM Content WHERE title = ? AND section_id = (SELECT id FROM Sections WHERE name = ? AND type = ?)", (current_subsection, selected_section, current_section_type))[0][0]
       
        # Insert a deletion request into the DeletionRequests table
        query = """
        INSERT INTO DeletionRequests (content_id, user)
        VALUES (?, ?)
        """
        execute_query(query, (content_id, os.getlogin()))
        add_notification(os.getlogin(), f"Your delete request for '{current_subsection}' has been submitted for approval.")
        messagebox.showinfo("Delete Content", "Deletion request submitted successfully.")
       
        # Display the pending delete request
        content_textbox.config(state=tk.NORMAL)
        content_textbox.delete("1.0", tk.END)
        content_textbox.insert(tk.END, "Pending delete request:\n\n")
        apply_tags(content_textbox, fetch_query("SELECT description FROM Content WHERE id = ?", (content_id,))[0][0], search_entry.get().strip())
        content_textbox.config(state=tk.DISABLED)
       
        disable_content()
        is_editing = False
        content_textbox.unbind("<Button-3>")

def get_selected_item(listbox):
    selection = listbox.curselection()
    return listbox.get(selection[0]) if selection else None

def enable_subsections():
    add_subsection_button.config(state=tk.NORMAL)
    edit_subsection_button.config(state=tk.NORMAL)
    delete_subsection_button.config(state=tk.NORMAL)

def disable_subsections():
    add_subsection_button.config(state=tk.DISABLED)
    edit_subsection_button.config(state=tk.DISABLED)
    delete_subsection_button.config(state=tk.DISABLED)

def bind_right_click_menu(text_widget):
    text_widget.unbind("<Button-3>")
    if is_editing:
        text_widget.bind("<Button-3>", show_formatting_bar)  # Right-click
        text_widget.bind("<Button-1>", hide_formatting_bar)  # Left-click outside
        text_widget.bind("<KeyRelease>", hide_formatting_bar)  # Hide when releasing a key

def show_formatting_bar(event):
    formatting_bar.pack(side=tk.TOP, fill=tk.X)

def hide_formatting_bar(event):
    if not any(tag in content_textbox.tag_names(tk.SEL_FIRST) for tag in ['highlight']):
        formatting_bar.pack_forget()

def open_edit_window():
    if current_subsection is None:
        messagebox.showwarning("Selection Error", "Please select a subsection to edit content.")
        return

    global formatting_bar

    edit_window = tk.Toplevel(root)
    edit_window.title("Edit Content")

    edit_textbox = tk.Text(edit_window, font=("Arial", 10), height=30, width=100)
    edit_textbox.pack(fill=tk.BOTH, expand=True)

    # Load current content or pending content
    content_id = fetch_query("SELECT id FROM Content WHERE title = ? AND section_id = (SELECT id FROM Sections WHERE name = ? AND type = ?)", (current_subsection, current_parent_section, current_section_type))[0][0]
    pending_content = fetch_query("SELECT pending_description FROM PendingContent WHERE content_id = ? AND user = ?", (content_id, os.getlogin()))

    if pending_content:
        # edit_textbox.insert(tk.END, "Content sent for approval:\n\n")
        edit_textbox.insert(tk.END, pending_content[0][0])
    else:
        content = fetch_query("SELECT description FROM Content WHERE id = ?", (content_id,))
        if content and content[0][0]:
            edit_textbox.insert(tk.END, content[0][0])
   
    right_click_menu = tk.Menu(edit_window, tearoff=0)
    right_click_menu.add_command(label="Bold", command=lambda: toggle_bold(edit_textbox))
    right_click_menu.add_command(label="Italic", command=lambda: toggle_italic(edit_textbox))
    right_click_menu.add_command(label="Underline", command=lambda: toggle_underline(edit_textbox))
    right_click_menu.add_command(label="Bullet Points", command=lambda: insert_bullet_points(edit_textbox))
    right_click_menu.add_command(label="Insert Hyperlink", command=lambda: insert_hyperlink(edit_textbox))
    right_click_menu.add_command(label="Undo Formatting", command=lambda: undo_formatting(edit_textbox))

    def show_right_click_menu(event):
        try:
            selected_text = edit_textbox.selection_get()
            if selected_text:
                right_click_menu.post(event.x_root, event.y_root)
        except tk.TclError:
            pass

    edit_textbox.bind("<Button-3>", show_right_click_menu)    

    def save_edited_content():
        new_content_description = edit_textbox.get("1.0", tk.END).strip()
        new_content="Content sent for approval:\n"+new_content_description

        if new_content:
            if pending_content:
                query = """
                UPDATE PendingContent SET pending_description = ? WHERE content_id = ? AND user = ?
                """
                execute_query(query, (new_content, content_id, os.getlogin()))
            else:
                query = """
                INSERT INTO PendingContent (content_id, pending_description, user)
                VALUES (?, ?, ?)
                """
                execute_query(query, (content_id, new_content, os.getlogin()))

            add_notification(os.getlogin(), f"Your edit reqg   uest for '{current_subsection}' has been submitted for approval.")
            messagebox.showinfo("Save Content", "Content saved and sent for approval.")
            load_content(current_subsection)
            edit_window.destroy()
        else:
            messagebox.showwarning("Input Error", "Description is required.")

    save_button = ttk.Button(edit_window, text="Save", command=save_edited_content)
    save_button.pack(side=tk.LEFT, padx=5, pady=5)

    cancel_button = ttk.Button(edit_window, text="Cancel", command=edit_window.destroy)
    cancel_button.pack(side=tk.RIGHT, padx=5, pady=5)

# Function to open links
def open_link(event):
    text_widget = event.widget
    x, y = event.x, event.y
    index = text_widget.index(f"@{x},{y}")
    for (start, end), url in hyperlink_ranges.items():
        if text_widget.compare(start, "<=", index) and text_widget.compare(end, ">=", index):
            webbrowser.open(url)
            return


def toggle_bold(text_widget):
    selected_text = text_widget.selection_get()
    if selected_text:
        text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        text_widget.insert(tk.INSERT, f'**{selected_text}**')

def toggle_italic(text_widget):
    selected_text = text_widget.selection_get()
    if selected_text:
        text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        text_widget.insert(tk.INSERT, f'*{selected_text}*')

def toggle_underline(text_widget):
    selected_text = text_widget.selection_get()
    if selected_text:
        text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        text_widget.insert(tk.INSERT, f'__{selected_text}__')

def insert_bullet_points(text_widget):
    selected_text = text_widget.selection_get()
    if selected_text:
        lines = selected_text.split('\n')
        for i, line in enumerate(lines):
            lines[i] = '- ' + line
        text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        text_widget.insert(tk.INSERT, '\n'.join(lines))

def insert_hyperlink(text_widget):
    url = simpledialog.askstring("Insert Hyperlink", "Enter URL:")
    if url:
        selected_text = text_widget.selection_get()
        if selected_text:
            text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            text_widget.insert(tk.INSERT, f'[{selected_text}]({url})')

def undo_formatting(text_widget):
    try:
        selected_text = text_widget.selection_get()
        start_index = text_widget.index(tk.SEL_FIRST)
        end_index = text_widget.index(tk.SEL_LAST)

        formatted_text = selected_text
        formatted_text = formatted_text.replace('**', '')
        formatted_text = formatted_text.replace('*', '')
        formatted_text = formatted_text.replace('__', '')
        formatted_text = formatted_text.replace('- ', '')
        formatted_text = formatted_text.replace('[', '')
        formatted_text = formatted_text.replace(']', '')
        formatted_text = formatted_text.replace('(', '')
        formatted_text = formatted_text.replace(')', '')

        text_widget.delete(start_index, end_index)
        text_widget.insert(start_index, formatted_text)
    except tk.TclError:
        messagebox.showwarning("Selection Error", "Please select text to remove formatting.")

def add_notification(user, message):
    query = """
    INSERT INTO Notifications (user, message, is_read)
    VALUES (?, ?, 0)
    """
    execute_query(query, (user, message))

def open_notifications():
    def search_notifications():
        query = search_entry.get().strip()
        filtered_notifications = [n for n in notifications if query.lower() in n[2].lower()]
        populate_notifications(filtered_notifications)

    def populate_notifications(notifications):
        for_approval_listbox.delete(0, tk.END)
        approved_listbox.delete(0, tk.END)
        rejected_listbox.delete(0, tk.END)
        for notification in notifications:
            notification_text = f"{notification[1]} - {notification[2]}"
            if "for approval" in notification[2].lower():
                for_approval_listbox.insert(tk.END, notification_text)
            elif "approved" in notification[2].lower():
                approved_listbox.insert(tk.END, notification_text)
            elif "rejected" in notification[2].lower():
                rejected_listbox.insert(tk.END, notification_text)

    def delete_selected_notification():
        selected_for_approval = for_approval_listbox.curselection()
        selected_approved = approved_listbox.curselection()
        selected_rejected = rejected_listbox.curselection()

        if selected_for_approval:
            selected = selected_for_approval[0]
            notification_text = for_approval_listbox.get(selected)
            for_approval_listbox.delete(selected)
        elif selected_approved:
            selected = selected_approved[0]
            notification_text = approved_listbox.get(selected)
            approved_listbox.delete(selected)
        elif selected_rejected:
            selected = selected_rejected[0]
            notification_text = rejected_listbox.get(selected)
            rejected_listbox.delete(selected)
        else:
            messagebox.showwarning("Selection Error", "Please select a notification to delete.")
            return

        # Remove from database
        notification_id = [n[0] for n in notifications if f"{n[1]} - {n[2]}" == notification_text][0]
        execute_query("DELETE FROM Notifications WHERE id = ?", (notification_id,))

    def clear_all_notifications():
        if messagebox.askyesno("Clear All Notifications", "Are you sure you want to clear all notifications?"):
            execute_query("DELETE FROM Notifications")
            for_approval_listbox.delete(0, tk.END)
            approved_listbox.delete(0, tk.END)
            rejected_listbox.delete(0, tk.END)

    def mark_as_read():
        selected_for_approval = for_approval_listbox.curselection()
        selected_approved = approved_listbox.curselection()
        selected_rejected = rejected_listbox.curselection()

        if selected_for_approval:
            selected = selected_for_approval[0]
            notification_text = for_approval_listbox.get(selected)
        elif selected_approved:
            selected = selected_approved[0]
            notification_text = approved_listbox.get(selected)
        elif selected_rejected:
            selected = selected_rejected[0]
            notification_text = rejected_listbox.get(selected)
        else:
            messagebox.showwarning("Selection Error", "Please select a notification to mark as read.")
            return

        notification_id = [n[0] for n in notifications if f"{n[1]} - {n[2]}" == notification_text][0]
        execute_query("UPDATE Notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        messagebox.showinfo("Marked as Read", "Notification has been marked as read.")
    
    def cancel_search():
        search_entry.delete(0, tk.END)
        populate_notifications(notifications)


    notifications_window = tk.Toplevel(root)
    notifications_window.title("Notifications")

    search_frame = ttk.Frame(notifications_window)
    search_frame.pack(fill=tk.X, pady=5)
    search_label = ttk.Label(search_frame, text="Search Notifications:")
    search_label.pack(side=tk.LEFT, padx=5)
    search_entry = ttk.Entry(search_frame, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)
    search_button = ttk.Button(search_frame, text="Search", command=search_notifications)
    search_button.pack(side=tk.LEFT, padx=5)
    cancel_search_button = ttk.Button(search_frame, text="Cancel Search", command=cancel_search)
    cancel_search_button.pack(side=tk.LEFT, padx=5)

    frame = ttk.Frame(notifications_window)
    frame.pack(fill=tk.BOTH, expand=True)

    for_approval_label = ttk.Label(frame, text="For Approval")
    for_approval_label.grid(row=0, column=0, padx=10, pady=5)
    approved_label = ttk.Label(frame, text="Approved")
    approved_label.grid(row=0, column=1, padx=10, pady=5)
    rejected_label = ttk.Label(frame, text="Rejected")
    rejected_label.grid(row=0, column=2, padx=10, pady=5)

    for_approval_listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=("Arial", 10))
    for_approval_listbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
    approved_listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=("Arial", 10))
    approved_listbox.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")
    rejected_listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=("Arial", 10))
    rejected_listbox.grid(row=1, column=2, padx=10, pady=5, sticky="nsew")

    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)
    frame.columnconfigure(2, weight=1)
    frame.rowconfigure(1, weight=1)

    buttons_frame = ttk.Frame(notifications_window)
    buttons_frame.pack(fill=tk.X, pady=5)

    mark_as_read_button = ttk.Button(buttons_frame, text="Mark as Read", command=mark_as_read)
    mark_as_read_button.pack(side=tk.LEFT, padx=5)
    delete_notification_button = ttk.Button(buttons_frame, text="Delete Notification", command=delete_selected_notification)
    delete_notification_button.pack(side=tk.LEFT, padx=5)
    clear_notifications_button = ttk.Button(buttons_frame, text="Clear All Notifications", command=clear_all_notifications)
    clear_notifications_button.pack(side=tk.LEFT, padx=5)

    notifications = fetch_notifications()
    populate_notifications(notifications)

def fetch_notifications():
    user = os.getlogin()
    query = "SELECT id, user, message, is_read FROM Notifications WHERE user = ?"
    return fetch_query(query, (user,))



   
def open_admin_dashboard():
    def search_approvals():
        query = search_entry.get().strip()
        filtered_edits = [e for e in pending_edits if query.lower() in e[2].lower()]
        filtered_deletions = [d for d in pending_deletions if query.lower() in d[2].lower()]
        populate_approvals(filtered_edits, filtered_deletions)

    def populate_approvals(edits, deletions):
        edit_approval_listbox.delete(0, tk.END)
        delete_approval_listbox.delete(0, tk.END)
        for edit in edits:
            content_title_result = fetch_query("SELECT title FROM Content WHERE id = ?", (edit[1],))
            if content_title_result:
                content_title = content_title_result[0][0]
                edit_approval_listbox.insert(tk.END, f"Edit: {content_title} - {edit[3]}")
            else:
                edit_approval_listbox.insert(tk.END, f"Edit: Content ID {edit[1]} (not found) - {edit[3]}")
        for deletion in deletions:
            content_title_result = fetch_query("SELECT title FROM Content WHERE id = ?", (deletion[1],))
            if content_title_result:
                content_title = content_title_result[0][0]
                delete_approval_listbox.insert(tk.END, f"Delete: {content_title} - {deletion[2]}")
            else:
                delete_approval_listbox.insert(tk.END, f"Delete: Content ID {deletion[1]} (not found) - {deletion[2]}")

    if os.getlogin() not in ADMIN_USERS:
        messagebox.showwarning("Access Denied", "You do not have permission to access the admin dashboard.")
        return
    def cancel_search():
        search_entry.delete(0, tk.END)
        populate_approvals(pending_edits, pending_deletions)


    admin_window = tk.Toplevel(root)
    admin_window.title("Admin Dashboard")

    search_frame = ttk.Frame(admin_window)
    search_frame.pack(fill=tk.X, pady=5)
    search_label = ttk.Label(search_frame, text="Search Approvals:")
    search_label.pack(side=tk.LEFT, padx=5)
    search_entry = ttk.Entry(search_frame, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)
    search_button = ttk.Button(search_frame, text="Search", command=search_approvals)
    search_button.pack(side=tk.LEFT, padx=5)
    cancel_search_button = ttk.Button(search_frame, text="Cancel Search", command=cancel_search)
    cancel_search_button.pack(side=tk.LEFT, padx=5)


    frame = ttk.Frame(admin_window)
    frame.pack(fill=tk.BOTH, expand=True)

    edit_approval_label = ttk.Label(frame, text="Edit Approval")
    edit_approval_label.grid(row=0, column=0, padx=10, pady=5)
    delete_approval_label = ttk.Label(frame, text="Delete Approval")
    delete_approval_label.grid(row=0, column=1, padx=10, pady=5)

    edit_approval_listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=("Arial", 10))
    edit_approval_listbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
    delete_approval_listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=("Arial", 10))
    delete_approval_listbox.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")

    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(1, weight=1)

    
    pending_edits = fetch_query("SELECT id, content_id, REPLACE(pending_description, 'Content sent for approval:', '') AS pending_description, user FROM PendingContent")
    pending_deletions = fetch_query("SELECT id, content_id, user FROM DeletionRequests")
    populate_approvals(pending_edits, pending_deletions)

    def highlight_differences(approved_text, pending_text):
        differ = difflib.Differ()
        diff = list(differ.compare(approved_text.splitlines(), pending_text.splitlines()))
        print(diff)
        differences = []
        for line in diff:
            if line.startswith("+ "):
                differences.append((line[2:], 'add'))
            elif line.startswith("- "):
                differences.append((line[2:], 'delete'))
            else:
                differences.append((line[2:], None))
        return differences

    def show_request_content(event):
        selected = event.widget.curselection()
        if not selected:
            return
        selected_text = event.widget.get(selected[0])
        if selected_text.startswith("Edit:"):
            request = pending_edits[selected[0]]
            content_id = request[1]
            pending_description = request[2]
            content_title_result = fetch_query("SELECT title, description FROM Content WHERE id = ?", (content_id,))
            if content_title_result:
                content_title = content_title_result[0][0]
                approved_description = content_title_result[0][1]
            else:
                content_title = f"Content ID {content_id} (not found)"
                approved_description = "No approved content available."

            content_window = tk.Toplevel(admin_window)
            content_window.title(f"Edit Request - {content_title}")

            approved_label = ttk.Label(content_window, text="Approved Content")
            approved_label.pack(pady=5)
            approved_textbox = tk.Text(content_window, font=("Arial", 10), height=15, width=80)
            approved_textbox.pack(fill=tk.BOTH, expand=True)
            if approved_description:
                approved_textbox.insert(tk.END, approved_description)
            approved_textbox.config(state=tk.DISABLED)

            pending_label = ttk.Label(content_window, text="Pending Changes")
            pending_label.pack(pady=5)
            pending_textbox = tk.Text(content_window, font=("Arial", 10), height=15, width=80)
            pending_textbox.pack(fill=tk.BOTH, expand=True)

            pending_textbox.tag_configure("add", background="lightgreen")
            pending_textbox.tag_configure("delete", background="lightcoral")

            print(approved_description)
            print('see the difference')
            print(pending_description)
        

            differences = highlight_differences(approved_description, pending_description)
        
            for line, tag in differences:
                pending_textbox.insert(tk.END, line + "\n", tag if tag else None) 
            def format_as_readable():
                pending_textbox.config(state=tk.NORMAL)
                apply_tags(pending_textbox, pending_description)
                pending_textbox.config(state=tk.DISABLED)
                pending_textbox.tag_configure('bold', font=('Arial', 10, 'bold'))
                pending_textbox.tag_configure('italic', font=('Arial', 10, 'italic'))
                pending_textbox.tag_configure('underline', font=('Arial', 10, 'underline'))
                pending_textbox.tag_configure('hyperlink', foreground='blue', underline=True)

            def save_changes():
                # Get the content from the pending_textbox
                pending_description = pending_textbox.get("1.0", tk.END).strip()
                # Execute the update query (replace 'content_id' with your actual variable)
                execute_query("UPDATE PendingContent SET pending_description = ? WHERE content_id = ?", (pending_description, content_id))
                content_window.destroy()
                admin_window.destroy()
                messagebox.showinfo("Approval", "Content edited successfully! Need to approve.")
            def readData():
                
                pending_description = pending_textbox.get("1.0", tk.END).strip()
              
            button_frame = ttk.Frame(content_window)
            button_frame.pack(side=tk.BOTTOM,pady=10)
            
            save_button = ttk.Button(button_frame, text="Save", command=save_changes)
            save_button.pack(side=tk.LEFT,padx=5)
            
            
            def toggle_read_edit():
                if toggle_button['text'] == "Read":
                    # Switch to "Read" mode
                    pending_textbox.config(state=tk.NORMAL)
                    
                    apply_tags(pending_textbox, pending_description)

                    pending_textbox.tag_configure('bold', font=('Arial', 10, 'bold'))
                    pending_textbox.tag_configure('italic', font=('Arial', 10, 'italic'))
                    pending_textbox.tag_configure('underline', font=('Arial', 10, 'underline'))
                    pending_textbox.tag_configure('hyperlink', foreground='blue', underline=True)
                    pending_textbox.config(state = tk.DISABLED)
                    toggle_button.config(text="Edit")
                    

                else:
                    # Switch to "Edit" mode
                    pending_textbox.config(state=tk.NORMAL)
                    
                    
                    
                    pending_textbox.insert(tk.END, pending_description)
                    pending_textbox.config(state=tk.NORMAL)
                    
                    pending_textbox.tag_configure("add", background="lightgreen")
                    pending_textbox.tag_configure("delete", background="lightcoral")
                    pending_textbox.delete("1.0",tk.END)
                    differences = highlight_differences(approved_description, pending_description)
                    for line, tag in differences:
                        print(pending_textbox.insert(tk.END, line + "\n", tag if tag else None))
                    toggle_button.config(text="Read")
                    
            approved_textbox.config(state=tk.NORMAL)
            apply_tags(approved_textbox,approved_description)
            approved_textbox.config(state=tk.DISABLED)
            approved_textbox.tag_configure('bold', font=('Arial', 10, 'bold'))
            approved_textbox.tag_configure('italic', font=('Arial', 10, 'italic'))
            approved_textbox.tag_configure('underline', font=('Arial', 10, 'underline'))
            approved_textbox.tag_configure('hyperlink', foreground='blue', underline=True)
            
            toggle_button = ttk.Button(button_frame, text="Read", command=toggle_read_edit)
            toggle_button.pack(side=tk.LEFT,padx=5)
      

            # pending_textbox.config(state=tk.DISABLED)

        elif selected_text.startswith("Delete:"):
            request = pending_deletions[selected[0] - len(pending_edits)]
            content_id = request[1]
            content_title_result = fetch_query("SELECT title, description FROM Content WHERE id = ?", (content_id,))
            if content_title_result:
                content_title = content_title_result[0][0]
                approved_description = content_title_result[0][1]
            else:
                content_title = f"Content ID {content_id} (not found)"
                approved_description = "No approved content available."

            content_window = tk.Toplevel(admin_window)
            content_window.title(f"Delete Request - {content_title}")

            approved_label = ttk.Label(content_window, text="Approved Content")
            approved_label.pack(pady=5)
            approved_textbox = tk.Text(content_window, font=("Arial", 10), height=15, width=80)
            approved_textbox.pack(fill=tk.BOTH, expand=True)
            if approved_description:
                approved_textbox.insert(tk.END, approved_description)
            approved_textbox.config(state=tk.DISABLED)

    edit_approval_listbox.bind("<<ListboxSelect>>", show_request_content)
    delete_approval_listbox.bind("<<ListboxSelect>>", show_request_content)

    def approve():
        selected = edit_approval_listbox.curselection() or delete_approval_listbox.curselection()
        if not selected:
            messagebox.showwarning("Selection Error", "Please select a request to approve.")
            return
        selected_text = edit_approval_listbox.get(selected[0]) if edit_approval_listbox.curselection() else delete_approval_listbox.get(selected[0])
        if selected_text.startswith("Edit:"):
            edit_id = pending_edits[selected[0]][0]
            content_id = pending_edits[selected[0]][1]
            pending_description = pending_edits[selected[0]][2]
            cleaned_text = pending_description.lstrip()
            execute_query("UPDATE Content SET description = ?, is_approved = 1 WHERE id = ?", (cleaned_text, content_id))
            execute_query("DELETE FROM PendingContent WHERE id = ?", (edit_id,))
            messagebox.showinfo("Approval", "Content edit approved successfully.")
            add_notification(fetch_query("SELECT user FROM Content WHERE id = ?", (content_id,))[0][0], f"Your edit request for '{selected_text}' has been approved.")
            edit_approval_listbox.delete(selected[0])
        elif selected_text.startswith("Delete:"):
            deletion_id = pending_deletions[selected[0] - len(pending_edits)][0]
            content_id = pending_deletions[selected[0] - len(pending_edits)][1]
            execute_query("UPDATE Content SET description = '' WHERE id = ?", (content_id,))
            execute_query("DELETE FROM DeletionRequests WHERE id = ?", (deletion_id,))
            execute_query("DELETE FROM PendingContent WHERE content_id = ?", (content_id,))
            messagebox.showinfo("Approval", "Content deletion approved successfully.")
            add_notification(fetch_query("SELECT user FROM Content WHERE id = ?", (content_id,))[0][0], f"Your delete request for '{selected_text}' has been approved.")
            delete_approval_listbox.delete(selected[0])
        if current_subsection:
            load_content(current_subsection)

    def reject():
        selected = edit_approval_listbox.curselection() or delete_approval_listbox.curselection()
        if not selected:
            messagebox.showwarning("Selection Error", "Please select a request to reject.")
            return
        selected_text = edit_approval_listbox.get(selected[0]) if edit_approval_listbox.curselection() else delete_approval_listbox.get(selected[0])
        if selected_text.startswith("Edit:"):
            edit_id = pending_edits[selected[0]][0]
            content_id = pending_edits[selected[0]][1]
            execute_query("DELETE FROM PendingContent WHERE id = ?", (edit_id,))
            messagebox.showinfo("Rejection", "Content edit rejected successfully.")
            add_notification(fetch_query("SELECT user FROM Content WHERE id = ?", (content_id,))[0][0], f"Your edit request for '{selected_text}' has been rejected.")
            edit_approval_listbox.delete(selected[0])
        elif selected_text.startswith("Delete:"):
            deletion_id = pending_deletions[selected[0] - len(pending_edits)][0]
            content_id = pending_deletions[selected[0] - len(pending_edits)][1]
            execute_query("DELETE FROM DeletionRequests WHERE id = ?", (deletion_id,))
            messagebox.showinfo("Rejection", "Content deletion request rejected successfully.")
            add_notification(fetch_query("SELECT user FROM Content WHERE id = ?", (content_id,))[0][0], f"Your delete request for '{selected_text}' has been rejected.")
            delete_approval_listbox.delete(selected[0])
        if current_subsection:
            load_content(current_subsection)

    approve_button = ttk.Button(admin_window, text="Approve", command=approve)
    approve_button.pack(side=tk.LEFT, padx=5, pady=5)

    reject_button = ttk.Button(admin_window, text="Reject", command=reject)
    reject_button.pack(side=tk.RIGHT, padx=5, pady=5)


           


# Create main window
root = tk.Tk()
root.title("U400 Helpdesk")
root.geometry("1272x1080")

style = ttk.Style(root)
style.theme_use("clam")

style.configure("TLabel", font=("Arial", 12))
style.configure("TButton", font=("Arial", 10))
style.configure("TEntry", font=("Arial", 10))
style.configure("TListbox", font=("Arial", 10))
style.configure("TText", font=("Arial", 10))

root.columnconfigure(0, weight=1)
root.rowconfigure(1, weight=1)

search_frame = ttk.Frame(root, padding="10 10 10 10")
search_frame.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
search_frame.columnconfigure(1, weight=1)

search_label = ttk.Label(search_frame, text="Search Box")
search_label.grid(row=0, column=0, sticky=tk.W)

search_entry = ttk.Entry(search_frame, width=50)
search_entry.grid(row=0, column=1, padx=5, sticky=tk.EW)
search_button = ttk.Button(search_frame, text="Search", command=update_listboxes)
search_button.grid(row=0, column=2, padx=5)

search_entry.bind('<KeyRelease>', update_listboxes)

container_frame = ttk.Frame(root)
container_frame.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
container_frame.columnconfigure(0, weight=1)
container_frame.rowconfigure(0, weight=1)

content_canvas = tk.Canvas(container_frame)
content_canvas.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)

content_scrollbar = ttk.Scrollbar(container_frame, orient="vertical", command=content_canvas.yview)
content_scrollbar.grid(row=0, column=1, sticky=tk.N + tk.S)

content_canvas.configure(yscrollcommand=content_scrollbar.set)

menu_frame = ttk.Frame(content_canvas, padding="10 10 10 10")
menu_frame.columnconfigure(0, weight=1)
menu_frame.rowconfigure(0, weight=1)

canvas_window = content_canvas.create_window((0, 0), window=menu_frame, anchor="nw")

def on_frame_configure(event):
    content_canvas.configure(scrollregion=content_canvas.bbox("all"))

menu_frame.bind("<Configure>", on_frame_configure)

def on_canvas_configure(event):
    canvas_width = event.width
    content_canvas.itemconfig(canvas_window, width=canvas_width)

content_canvas.bind("<Configure>", on_canvas_configure)

def _on_mouse_wheel(event):
    content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

content_canvas.bind_all("<MouseWheel>", _on_mouse_wheel)

menu_frame.columnconfigure(0, weight=1, uniform="group1")
menu_frame.columnconfigure(1, weight=1, uniform="group1")
menu_frame.columnconfigure(2, weight=1, uniform="group1")
menu_frame.rowconfigure(0, weight=1)

functions_frame = ttk.Frame(menu_frame, padding="10 10 10 10")
functions_frame.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
functions_frame.columnconfigure(0, weight=1)
functions_frame.rowconfigure(1, weight=1)

functions_label = ttk.Label(functions_frame, text="Functions")
functions_label.grid(row=0, column=0, sticky=tk.W)

functions_list_frame = ttk.Frame(functions_frame)
functions_list_frame.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
functions_list_frame.columnconfigure(0, weight=1)
functions_list_frame.rowconfigure(0, weight=1)

functions_list_scrollbar = ttk.Scrollbar(functions_list_frame, orient="vertical")
functions_list_scrollbar.grid(row=0, column=1, sticky=tk.N + tk.S)

functions_list = tk.Listbox(functions_list_frame, selectmode=tk.SINGLE, font=("Arial", 10), yscrollcommand=functions_list_scrollbar.set)
functions_list.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
functions_list_scrollbar.config(command=functions_list.yview)

functions_buttons_frame = ttk.Frame(functions_frame)
functions_buttons_frame.grid(row=2, column=0, pady=5)
add_function_button = ttk.Button(functions_buttons_frame, text="Add Function", command=lambda: add_section("Functions"))
add_function_button.grid(row=0, column=0, padx=5)
edit_function_button = ttk.Button(functions_buttons_frame, text="Edit Function", command=lambda: edit_section("Functions"))
edit_function_button.grid(row=0, column=1, padx=5)
delete_function_button = ttk.Button(functions_buttons_frame, text="Delete Function", command=lambda: delete_section("Functions"))
delete_function_button.grid(row=0, column=2, padx=5)

design_frame = ttk.Frame(menu_frame, padding="10 10 10 10")
design_frame.grid(row=0, column=1, sticky=tk.N + tk.S + tk.E + tk.W)
design_frame.columnconfigure(0, weight=1)
design_frame.rowconfigure(1, weight=1)

design_label = ttk.Label(design_frame, text="Important Design Aspects")
design_label.grid(row=0, column=0, sticky=tk.W)

design_list_frame = ttk.Frame(design_frame)
design_list_frame.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
design_list_frame.columnconfigure(0, weight=1)
design_list_frame.rowconfigure(0, weight=1)

design_list_scrollbar = ttk.Scrollbar(design_list_frame, orient="vertical")
design_list_scrollbar.grid(row=0, column=1, sticky=tk.N + tk.S)

design_list = tk.Listbox(design_list_frame, selectmode=tk.SINGLE, font=("Arial", 10), yscrollcommand=design_list_scrollbar.set)
design_list.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
design_list_scrollbar.config(command=design_list.yview)

design_buttons_frame = ttk.Frame(design_frame)
design_buttons_frame.grid(row=2, column=0, pady=5)
add_design_button = ttk.Button(design_buttons_frame, text="Add Design Aspect", command=lambda: add_section("Important Design Aspects"))
add_design_button.grid(row=0, column=0, padx=5)
edit_design_button = ttk.Button(design_buttons_frame, text="Edit Design Aspect", command=lambda: edit_section("Important Design Aspects"))
edit_design_button.grid(row=0, column=1, padx=5)
delete_design_button = ttk.Button(design_buttons_frame, text="Delete Design Aspect", command=lambda: delete_section("Important Design Aspects"))
delete_design_button.grid(row=0, column=2, padx=5)

interfaces_frame = ttk.Frame(menu_frame, padding="10 10 10 10")
interfaces_frame.grid(row=0, column=2, sticky=tk.N + tk.S + tk.E + tk.W)
interfaces_frame.columnconfigure(0, weight=1)
interfaces_frame.rowconfigure(1, weight=1)

interfaces_label = ttk.Label(interfaces_frame, text="Interfaces")
interfaces_label.grid(row=0, column=0, sticky=tk.W)

interfaces_list_frame = ttk.Frame(interfaces_frame)
interfaces_list_frame.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
interfaces_list_frame.columnconfigure(0, weight=1)
interfaces_list_frame.rowconfigure(0, weight=1)

interfaces_list_scrollbar = ttk.Scrollbar(interfaces_list_frame, orient="vertical")
interfaces_list_scrollbar.grid(row=0, column=1, sticky=tk.N + tk.S)

interfaces_list = tk.Listbox(interfaces_list_frame, selectmode=tk.SINGLE, font=("Arial", 10), yscrollcommand=interfaces_list_scrollbar.set)
interfaces_list.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
interfaces_list_scrollbar.config(command=interfaces_list.yview)

interfaces_buttons_frame = ttk.Frame(interfaces_frame)
interfaces_buttons_frame.grid(row=2, column=0, pady=5)
add_interface_button = ttk.Button(interfaces_buttons_frame, text="Add Interface", command=lambda: add_section("Interfaces"))
add_interface_button.grid(row=0, column=0, padx=5)
edit_interface_button = ttk.Button(interfaces_buttons_frame, text="Edit Interface", command=lambda: edit_section("Interfaces"))
edit_interface_button.grid(row=0, column=1, padx=5)
delete_interface_button = ttk.Button(interfaces_buttons_frame, text="Delete Interface", command=lambda: delete_section("Interfaces"))
delete_interface_button.grid(row=0, column=2, padx=5)

menu_frame.columnconfigure(0, weight=1, uniform="group1")
menu_frame.columnconfigure(1, weight=1, uniform="group1")
menu_frame.columnconfigure(2, weight=1, uniform="group1")
menu_frame.rowconfigure(0, weight=1)

subsections_frame = ttk.Frame(menu_frame, padding="10 10 10 10")
subsections_frame.grid(row=1, column=0, columnspan=3, sticky=tk.N + tk.S + tk.E + tk.W)
subsections_frame.columnconfigure(0, weight=1)
subsections_frame.rowconfigure(1, weight=1)

subsections_label = ttk.Label(subsections_frame, text="Subsections")
subsections_label.grid(row=0, column=0, sticky=tk.W)

subsections_list_frame = ttk.Frame(subsections_frame)
subsections_list_frame.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
subsections_list_frame.columnconfigure(0, weight=1)
subsections_list_frame.rowconfigure(0, weight=1)

subsections_list_scrollbar = ttk.Scrollbar(subsections_list_frame, orient="vertical")
subsections_list_scrollbar.grid(row=0, column=1, sticky=tk.N + tk.S)

subsections_list = tk.Listbox(subsections_list_frame, selectmode=tk.SINGLE, font=("Arial", 10), yscrollcommand=subsections_list_scrollbar.set)
subsections_list.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
subsections_list_scrollbar.config(command=subsections_list.yview)

subsections_buttons_frame = ttk.Frame(subsections_frame)
subsections_buttons_frame.grid(row=2, column=0, pady=5)
add_subsection_button = ttk.Button(subsections_buttons_frame, text="Add Subsection", command=lambda: add_subsection(current_section_type))
add_subsection_button.grid(row=0, column=0, padx=5)
edit_subsection_button = ttk.Button(subsections_buttons_frame, text="Edit Subsection", command=lambda: edit_subsection(current_section_type))
edit_subsection_button.grid(row=0, column=1, padx=5)
delete_subsection_button = ttk.Button(subsections_buttons_frame, text="Delete Subsection", command=lambda: delete_subsection(current_section_type))
delete_subsection_button.grid(row=0, column=2, padx=5)

subsections_list.bind('<<ListboxSelect>>', on_select)

content_frame = ttk.Frame(menu_frame, padding="10 10 10 10")
content_frame.grid(row=2, column=0, columnspan=3, sticky=tk.N + tk.S + tk.E + tk.W)
content_frame.columnconfigure(0, weight=1)
content_frame.rowconfigure(1, weight=1)

content_label = ttk.Label(content_frame, text="Content")
content_label.grid(row=0, column=0, sticky=tk.W)

content_textbox_frame = ttk.Frame(content_frame)
content_textbox_frame.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
content_textbox_frame.columnconfigure(0, weight=1)
content_textbox_frame.rowconfigure(0, weight=1)

content_textbox_scrollbar = ttk.Scrollbar(content_textbox_frame, orient="vertical")
content_textbox_scrollbar.grid(row=0, column=1, sticky=tk.N + tk.S)

content_textbox = tk.Text(content_textbox_frame, font=("Arial", 10), wrap=tk.WORD, yscrollcommand=content_textbox_scrollbar.set)
content_textbox.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
content_textbox_scrollbar.config(command=content_textbox.yview)

# Define tags for formatting
content_textbox.tag_configure('bold', font=('Arial', 10, 'bold'))
content_textbox.tag_configure('italic', font=('Arial', 10, 'italic'))
content_textbox.tag_configure('underline', font=('Arial', 10, 'underline'))
content_textbox.tag_configure('hyperlink', foreground='blue', underline=True)

content_buttons_frame = ttk.Frame(content_frame)
content_buttons_frame.grid(row=2, column=0, pady=5)
edit_content_button = ttk.Button(content_buttons_frame, text="Edit Content", command=edit_content)
edit_content_button.grid(row=0, column=0, padx=5)
delete_content_button = ttk.Button(content_buttons_frame, text="Request Delete", command=delete_content)
delete_content_button.grid(row=0, column=1, padx=5)

# Bind hyperlink click event
content_textbox.tag_bind("hyperlink", "<Button-1>", open_link)

# Load initial data
load_listbox(functions_list, 'Functions')
load_listbox(design_list, 'Important Design Aspects')
load_listbox(interfaces_list, 'Interfaces')

disable_subsections()
disable_content()

# Admin button and notifications
if os.getlogin() in ADMIN_USERS:
    admin_button = ttk.Button(root, text="Admin Dashboard", command=open_admin_dashboard)
    admin_button.grid(row=3, column=0, padx=10, pady=10, sticky=tk.W)

notifications_button = ttk.Button(root, text="Notifications", command=open_notifications)
notifications_button.grid(row=3, column=0, padx=10, pady=10, sticky=tk.E)

root.mainloop()





