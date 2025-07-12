function toggleForm() {
      const form = document.getElementById('ask-form');
      form.style.display = form.style.display === 'none' ? 'block' : 'none';
    }

    async function submitQuestion() {
      const token = localStorage.getItem('token') || '';
      const response = await fetch('http://localhost:5000/api/questions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + token
        },
        body: JSON.stringify({
          title: document.getElementById('title').value,
          description: document.getElementById('description').value,
          tags: document.getElementById('tags').value.split(',')
        })
      });
      const data = await response.json();
      alert(data.message || 'Question submitted!');
    }

    async function vote(direction) {
      const token = localStorage.getItem('token') || '';
      const answerId = '123456'; // replace with dynamic answer ID
      const res = await fetch(`http://localhost:5000/api/answers/vote/${answerId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + token
        },
        body: JSON.stringify({ type: direction })
      });
      const data = await res.json();
      alert(data.message || data.error);
    }