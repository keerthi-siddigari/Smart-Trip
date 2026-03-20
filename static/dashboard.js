function toggleProfile() {
    const menu = document.getElementById("profileMenu");
    menu.classList.toggle("hidden");
}

let tripToDelete = null; // store the trip id temporarily

// Function to open delete modal
function deleteTrip(tripId) {
    tripToDelete = tripId;

    const deleteModal = document.getElementById('deleteModal');
    if (!deleteModal) return;

    deleteModal.classList.remove('hidden');

    // Show confirm content and hide success
    const confirmContent = document.getElementById('deleteConfirmContent');
    const successContent = document.getElementById('deleteSuccessContent');
    if (confirmContent) confirmContent.classList.remove('hidden');
    if (successContent) successContent.classList.add('hidden');
}

// Cancel delete
document.getElementById('cancelDelete')?.addEventListener('click', () => {
    tripToDelete = null;
    document.getElementById('deleteModal')?.classList.add('hidden');
});

// Confirm delete
// Confirm delete
document.getElementById('confirmDelete')?.addEventListener('click', () => {
    if (!tripToDelete) return;

    fetch(`/delete-trip/${tripToDelete}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Use the removeTripFromUI function!
            removeTripFromUI(tripToDelete, data.no_trips_left);

            // Show success content in modal
            const confirmContent = document.getElementById('deleteConfirmContent');
            const successContent = document.getElementById('deleteSuccessContent');
            if (confirmContent) confirmContent.classList.add('hidden');
            if (successContent) successContent.classList.remove('hidden');

            // Hide modal automatically after 2s
            setTimeout(() => {
                document.getElementById('deleteModal')?.classList.add('hidden');
                tripToDelete = null;
            }, 2000);

        } else {
            alert("Error: " + (data.message || "Unable to delete trip"));
        }
    })
    .catch(err => {
        console.error(err);
        tripToDelete = null;
        document.getElementById('deleteModal')?.classList.add('hidden');
        alert("Something went wrong!");
    });
});

function handleLogout() {

  const btn = document.getElementById("logoutBtn");

  btn.innerText = "Logging out...";
  btn.classList.add("opacity-70");
  btn.disabled = true;

  window.location.href = "/logout";
}

// After deleting a trip
function removeTripFromUI(tripId, noTripsLeft) {
    // Remove trip card and update stats
    const tripCard = document.querySelector(`[data-trip-id='${tripId}']`);
    if (tripCard) {
        const statusEl = tripCard.querySelector('span');
        const statusText = statusEl ? statusEl.textContent.trim() : '';

        tripCard.remove();

        // Update dashboard stats
        const totalEl = document.getElementById('total-trips');
        const upcomingEl = document.getElementById('upcoming-trips');
        const completedEl = document.getElementById('completed-trips');

        if (totalEl) totalEl.textContent = Math.max(0, parseInt(totalEl.textContent) - 1);
        if (statusText === 'Upcoming' && upcomingEl) upcomingEl.textContent = Math.max(0, parseInt(upcomingEl.textContent) - 1);
        if (statusText === 'Completed' && completedEl) completedEl.textContent = Math.max(0, parseInt(completedEl.textContent) - 1);
    }

    // Show "No trips yet" message if no trips left
    if (noTripsLeft) {
        const noTripsMsg = document.getElementById('no-trips-msg');
        if (noTripsMsg) noTripsMsg.classList.remove('hidden');
    }
}